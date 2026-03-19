#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <video.mp4|youtube-url> [output-dir] [model]" >&2
  echo "Env overrides: EVERY_N_FRAMES, INTERVAL_SECONDS, MAX_FRAMES, BATCH_SIZE, MAX_WIDTH, JPEG_QUALITY, ENABLE_AUDIO_TRANSCRIPT, AUDIO_BACKEND, LOCAL_ASR_MODEL, LOCAL_ASR_DEVICE, LOCAL_ASR_COMPUTE_TYPE, LOCAL_ASR_BEAM_SIZE, AUDIO_MODEL, AUDIO_LANGUAGE, STRICT_AUDIO, TEMP_AUDIO_FORMAT, SUMMARY_BACKEND, MAX_TRANSCRIPT_CHARS, MAX_KEYFRAMES_FOR_REVIEW, CHUNK_TRANSCRIPT_CHARS, PARALLEL_REQUESTS, VISION_DETAIL, SUMMARY_LANGUAGE, API_BASE, ENV_FILE, AUTO_INSTALL_FFMPEG, AUTO_SMART_SAMPLING" >&2
  exit 1
fi

INPUT_SOURCE="$1"
OUTPUT_DIR="${2:-./video-summary-$(date +%Y%m%d-%H%M%S)}"
MODEL="${3:-${VIDEO_SUMMARY_MODEL:-gpt-4.1-mini}}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INPUT_DIR="$OUTPUT_DIR/input"
FRAMES_DIR="$OUTPUT_DIR/frames"
MANIFEST_PATH="$FRAMES_DIR/frames_manifest.json"
SUMMARY_PATH="$OUTPUT_DIR/video_summary.md"
TRANSCRIPT_PATH="$OUTPUT_DIR/audio_transcript.txt"
TRANSCRIPT_SEGMENTS_PATH="$OUTPUT_DIR/audio_transcript.segments.json"
REVIEW_PACK_PATH="$OUTPUT_DIR/codex_review_pack.md"
INPUT_VIDEO=""

has_ffmpeg_tools() {
  command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1
}

ensure_ffmpeg() {
  if has_ffmpeg_tools; then
    return 0
  fi

  local mode="${AUTO_INSTALL_FFMPEG:-ask}"
  local consent="n"

  if [ "$mode" = "always" ]; then
    consent="y"
  elif [ "$mode" = "never" ]; then
    consent="n"
  else
    echo "[warn] ffmpeg/ffprobe nao foram encontrados no ambiente."
    echo "[question] Posso instalar o ffmpeg agora? Vai precisar de permissao de administrador e pode pedir sua senha."
    printf "> [s/N]: "
    local answer=""
    read -r answer || true
    case "${answer,,}" in
      s|sim|y|yes) consent="y" ;;
      *) consent="n" ;;
    esac
  fi

  if [ "$consent" != "y" ]; then
    echo "[error] Nao foi possivel continuar sem ffmpeg/ffprobe." >&2
    exit 1
  fi

  echo "[info] Iniciando instalacao do ffmpeg. O sistema pode solicitar senha de administrador."
  if ! "$SCRIPT_DIR/install_ffmpeg.sh"; then
    echo "[error] Falha na instalacao automatica do ffmpeg." >&2
    exit 1
  fi

  if ! has_ffmpeg_tools; then
    echo "[error] ffmpeg/ffprobe ainda nao estao disponiveis apos a instalacao." >&2
    exit 1
  fi
}

resolve_input_video() {
  if [ -f "$INPUT_SOURCE" ]; then
    INPUT_VIDEO="$INPUT_SOURCE"
    return 0
  fi

  mkdir -p "$INPUT_DIR"
  if ! INPUT_VIDEO="$(
    python3 "$SCRIPT_DIR/resolve_video_input.py" \
      --source "$INPUT_SOURCE" \
      --output-dir "$INPUT_DIR" \
      --output-name "source_video"
  )"; then
    echo "[error] Falha ao resolver input: $INPUT_SOURCE" >&2
    exit 1
  fi
}

get_video_duration_seconds() {
  local video_path="$1"
  ffprobe \
    -v error \
    -show_entries format=duration \
    -of default=noprint_wrappers=1:nokey=1 \
    "$video_path" 2>/dev/null || true
}

is_lte() {
  local lhs="$1"
  local rhs="$2"
  awk -v a="$lhs" -v b="$rhs" 'BEGIN {exit !(a <= b)}'
}

configure_smart_sampling_defaults() {
  if [ "${AUTO_SMART_SAMPLING:-1}" = "0" ]; then
    return 0
  fi

  if [ -n "${INTERVAL_SECONDS:-}" ] || [ -n "${EVERY_N_FRAMES:-}" ]; then
    return 0
  fi

  local duration
  duration="$(get_video_duration_seconds "$INPUT_VIDEO")"
  if [ -n "$duration" ]; then
    if is_lte "$duration" 120; then
      INTERVAL_SECONDS="${SMART_INTERVAL_SHORT:-0.5}"
    elif is_lte "$duration" 600; then
      INTERVAL_SECONDS="${SMART_INTERVAL_MEDIUM:-1.0}"
    elif is_lte "$duration" 1800; then
      INTERVAL_SECONDS="${SMART_INTERVAL_LONG:-2.0}"
    else
      INTERVAL_SECONDS="${SMART_INTERVAL_XLONG:-3.0}"
    fi
    echo "[info] Smart sampling selecionou INTERVAL_SECONDS=$INTERVAL_SECONDS (duracao ~${duration}s)."
  else
    INTERVAL_SECONDS="${SMART_INTERVAL_FALLBACK:-1.0}"
    echo "[info] Smart sampling fallback INTERVAL_SECONDS=$INTERVAL_SECONDS."
  fi

  if [ -z "${MAX_FRAMES:-}" ]; then
    MAX_FRAMES="${SMART_MAX_FRAMES:-180}"
    echo "[info] Smart sampling selecionou MAX_FRAMES=$MAX_FRAMES."
  fi
  if [ -z "${BATCH_SIZE:-}" ]; then
    BATCH_SIZE="${SMART_BATCH_SIZE:-16}"
    echo "[info] Smart sampling selecionou BATCH_SIZE=$BATCH_SIZE."
  fi
}

ensure_ffmpeg
resolve_input_video

if [ ! -f "$INPUT_VIDEO" ]; then
  echo "Input video not found: $INPUT_VIDEO" >&2
  exit 1
fi

configure_smart_sampling_defaults
mkdir -p "$FRAMES_DIR"

EXTRACT_CMD=(python3 "$SCRIPT_DIR/extract_frames.py" --input "$INPUT_VIDEO" --output-dir "$FRAMES_DIR")

if [ -n "${INTERVAL_SECONDS:-}" ]; then
  EXTRACT_CMD+=(--interval-seconds "$INTERVAL_SECONDS")
else
  EXTRACT_CMD+=(--every-n-frames "${EVERY_N_FRAMES:-15}")
fi
if [ -n "${MAX_FRAMES:-}" ]; then
  EXTRACT_CMD+=(--max-frames "$MAX_FRAMES")
fi
if [ -n "${MAX_WIDTH:-}" ]; then
  EXTRACT_CMD+=(--max-width "$MAX_WIDTH")
fi
if [ -n "${JPEG_QUALITY:-}" ]; then
  EXTRACT_CMD+=(--jpeg-quality "$JPEG_QUALITY")
fi

echo "[info] Extracting frames..."
"${EXTRACT_CMD[@]}"

if [ "${ENABLE_AUDIO_TRANSCRIPT:-1}" != "0" ]; then
  AUDIO_BACKEND="${AUDIO_BACKEND:-local}"
  if [ "$AUDIO_BACKEND" = "api" ]; then
    TRANS_CMD=(
      python3 "$SCRIPT_DIR/transcribe_audio_openai.py"
      --input "$INPUT_VIDEO"
      --output "$TRANSCRIPT_PATH"
      --model "${AUDIO_MODEL:-gpt-4o-mini-transcribe}"
      --language "${AUDIO_LANGUAGE:-pt}"
      --temp-audio-format "${TEMP_AUDIO_FORMAT:-mp3}"
    )
    if [ -n "${API_BASE:-}" ]; then
      TRANS_CMD+=(--api-base "$API_BASE")
    fi
    if [ -n "${ENV_FILE:-}" ]; then
      TRANS_CMD+=(--env-file "$ENV_FILE")
    fi
  else
    TRANS_CMD=(
      python3 "$SCRIPT_DIR/transcribe_audio_local.py"
      --input "$INPUT_VIDEO"
      --output "$TRANSCRIPT_PATH"
      --segments-json "$TRANSCRIPT_SEGMENTS_PATH"
      --model-size "${LOCAL_ASR_MODEL:-small}"
      --device "${LOCAL_ASR_DEVICE:-auto}"
      --compute-type "${LOCAL_ASR_COMPUTE_TYPE:-int8}"
      --beam-size "${LOCAL_ASR_BEAM_SIZE:-3}"
      --language "${AUDIO_LANGUAGE:-pt}"
    )
    if [ "${LOCAL_ASR_VAD_FILTER:-0}" = "1" ]; then
      TRANS_CMD+=(--vad-filter)
    fi
  fi

  echo "[info] Transcribing audio..."
  if "${TRANS_CMD[@]}"; then
    echo "[ok] Audio transcript generated."
  else
    TRANS_RC=$?
    if [ "$TRANS_RC" -eq 2 ]; then
      echo "[warn] Video has no audio stream; continuing with visual summary only."
    elif [ "$TRANS_RC" -eq 4 ]; then
      echo "[warn] Local ASR dependency missing; continuing with visual summary only."
      echo "[hint] Install local ASR: python3 -m pip install --upgrade faster-whisper"
    elif [ "${STRICT_AUDIO:-0}" = "1" ]; then
      echo "[error] Audio transcription failed and STRICT_AUDIO=1." >&2
      exit "$TRANS_RC"
    else
      echo "[warn] Audio transcription failed (rc=$TRANS_RC); continuing with visual summary only."
    fi
  fi
fi

SUMMARY_BACKEND="${SUMMARY_BACKEND:-codex-local}"
if [ "$SUMMARY_BACKEND" = "api" ]; then
  SUM_CMD=(
    python3 "$SCRIPT_DIR/summarize_frames_openai.py"
    --manifest "$MANIFEST_PATH"
    --model "$MODEL"
    --batch-size "${BATCH_SIZE:-12}"
    --detail "${VISION_DETAIL:-low}"
    --language "${SUMMARY_LANGUAGE:-pt-BR}"
    --max-transcript-chars "${MAX_TRANSCRIPT_CHARS:-12000}"
    --chunk-transcript-chars "${CHUNK_TRANSCRIPT_CHARS:-1200}"
    --parallel-requests "${PARALLEL_REQUESTS:-2}"
    --output "$SUMMARY_PATH"
  )
  if [ -n "${API_BASE:-}" ]; then
    SUM_CMD+=(--api-base "$API_BASE")
  fi
  if [ -n "${ENV_FILE:-}" ]; then
    SUM_CMD+=(--env-file "$ENV_FILE")
  fi
  if [ -s "$TRANSCRIPT_PATH" ]; then
    SUM_CMD+=(--transcript-file "$TRANSCRIPT_PATH")
  fi
  echo "[info] Summarizing frames with API backend..."
  "${SUM_CMD[@]}"
  echo "[ok] Done."
  echo "[ok] Summary: $SUMMARY_PATH"
else
  PACK_CMD=(
    python3 "$SCRIPT_DIR/prepare_codex_video_review.py"
    --manifest "$MANIFEST_PATH"
    --output-dir "$OUTPUT_DIR"
    --output "$REVIEW_PACK_PATH"
    --max-keyframes "${MAX_KEYFRAMES_FOR_REVIEW:-24}"
    --max-transcript-chars "${MAX_TRANSCRIPT_CHARS:-12000}"
  )
  if [ -s "$TRANSCRIPT_PATH" ]; then
    PACK_CMD+=(--transcript-file "$TRANSCRIPT_PATH")
  fi

  echo "[info] Preparing local review pack for Codex..."
  "${PACK_CMD[@]}"
  echo "[ok] Done."
  echo "[ok] Review pack: $REVIEW_PACK_PATH"
fi
