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

detect_hardware_profile() {
  local os_type
  os_type=$(uname -s)
  local arch_type
  arch_type=$(uname -m)
  
  local has_nvidia=0
  if command -v nvidia-smi >/dev/null 2>&1; then
    if nvidia-smi >/dev/null 2>&1; then
      has_nvidia=1
    fi
  fi
  
  local has_apple_silicon=0
  if [ "$os_type" = "Darwin" ] && [ "$arch_type" = "arm64" ]; then
    has_apple_silicon=1
  fi
  
  local cpu_cores
  if [ "$os_type" = "Darwin" ]; then
    cpu_cores=$(sysctl -n hw.logicalcpu 2>/dev/null || echo 4)
  else
    cpu_cores=$(nproc 2>/dev/null || echo 4)
  fi
  
  local hw_tier="low"
  if [ "$has_nvidia" -eq 1 ] || [ "$has_apple_silicon" -eq 1 ]; then
    hw_tier="high"
  elif [ "$cpu_cores" -ge 8 ]; then
    hw_tier="medium"
  else
    hw_tier="low"
  fi
  
  echo "$hw_tier"
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

  local hw_tier
  hw_tier="$(detect_hardware_profile)"
  local smart_asr_default="tiny"
  local smart_max_frames_default=180
  local smart_max_keyframes_default=24

  if [ "$hw_tier" = "high" ]; then
    smart_asr_default="small"
    smart_max_frames_default=360
    smart_max_keyframes_default=48
  elif [ "$hw_tier" = "medium" ]; then
    smart_asr_default="base"
    smart_max_frames_default=240
    smart_max_keyframes_default=36
  fi

  if [ -z "${LOCAL_ASR_MODEL:-}" ]; then
    LOCAL_ASR_MODEL="$smart_asr_default"
    echo "[info] Smart sampling selecionou LOCAL_ASR_MODEL=$LOCAL_ASR_MODEL baseado em hardware ($hw_tier)."
  fi
  if [ -z "${MAX_KEYFRAMES_FOR_REVIEW:-}" ]; then
    MAX_KEYFRAMES_FOR_REVIEW="$smart_max_keyframes_default"
    echo "[info] Smart sampling selecionou MAX_KEYFRAMES_FOR_REVIEW=$MAX_KEYFRAMES_FOR_REVIEW baseado em hardware ($hw_tier)."
  fi

  if [ -z "${MAX_FRAMES:-}" ]; then
    MAX_FRAMES="${SMART_MAX_FRAMES:-$smart_max_frames_default}"
    echo "[info] Smart sampling selecionou MAX_FRAMES=$MAX_FRAMES baseado em hardware ($hw_tier)."
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

echo "[info] Starting parallel processing (Extraction + Transcription)..."

# --- 1. Audio Transcription Setup ---
TRANS_CMD=()
if [ "${ENABLE_AUDIO_TRANSCRIPT:-1}" != "0" ]; then
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

# --- 2. Run background jobs ---
echo "[info] Extraction: Starting..."
"${EXTRACT_CMD[@]}" > "$OUTPUT_DIR/extract_frames.log" 2>&1 &
PID_EXTRACT=$!

PID_TRANS=""
if [ ${#TRANS_CMD[@]} -gt 0 ]; then
  echo "[info] Transcription: Starting..."
  "${TRANS_CMD[@]}" > "$OUTPUT_DIR/transcribe_audio.log" 2>&1 &
  PID_TRANS=$!
fi

# --- 3. Wait and monitor ---
TRANS_RC=0
if [ -n "$PID_TRANS" ]; then
  wait "$PID_TRANS" || TRANS_RC=$?
  if [ "$TRANS_RC" -eq 0 ]; then
    echo "[ok] Audio transcript generated."
  elif [ "$TRANS_RC" -eq 2 ]; then
    echo "[warn] Video has no audio stream; continuing with visual summary only."
  elif [ "$TRANS_RC" -eq 4 ]; then
    echo "[warn] Local ASR dependency missing (faster-whisper)."
  elif [ "${STRICT_AUDIO:-0}" = "1" ]; then
    echo "[error] Audio transcription failed (rc=$TRANS_RC) and STRICT_AUDIO=1." >&2
    exit "$TRANS_RC"
  else
    echo "[warn] Audio transcription failed (rc=$TRANS_RC); continuing with visual summary only."
  fi
fi

wait "$PID_EXTRACT"
echo "[ok] Frame extraction finished."


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
