#!/usr/bin/env python3
"""Extract audio from video and transcribe locally using faster-whisper."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, text=True, capture_output=True)


def has_audio_stream(video_path: Path) -> bool:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=codec_type",
        "-of",
        "csv=p=0",
        str(video_path),
    ]
    try:
        result = run_cmd(cmd)
    except FileNotFoundError:
        raise RuntimeError("ffprobe not found. Install ffmpeg package first.")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"ffprobe failed: {exc.stderr.strip()}") from exc
    return "audio" in result.stdout


def extract_audio_wav(video_path: Path, wav_path: Path) -> None:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(video_path),
        "-map",
        "0:a:0",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(wav_path),
    ]
    try:
        run_cmd(cmd)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found. Install ffmpeg package first.")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"ffmpeg audio extraction failed: {exc.stderr.strip()}") from exc


def hhmmss(seconds: float) -> str:
    total_ms = int(round(max(0.0, seconds) * 1000))
    s, ms = divmod(total_ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transcribe video audio locally with faster-whisper."
    )
    parser.add_argument("--input", required=True, type=Path, help="Input video file")
    parser.add_argument("--output", required=True, type=Path, help="Output transcript text file")
    parser.add_argument(
        "--segments-json",
        type=Path,
        help="Optional output JSON with timestamped segments",
    )
    parser.add_argument(
        "--model-size",
        default="small",
        help="Whisper model size: tiny, base, small, medium, large-v3, ...",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="Language hint (e.g. pt, en). Leave empty for auto-detect.",
    )
    parser.add_argument(
        "--device",
        default="auto",
        help="Device for inference: auto, cpu, cuda",
    )
    parser.add_argument(
        "--compute-type",
        default="int8",
        help="faster-whisper compute type (int8, int8_float16, float16, float32)",
    )
    parser.add_argument(
        "--beam-size",
        type=int,
        default=3,
        help="Beam size for transcription decoding",
    )
    parser.add_argument(
        "--vad-filter",
        action="store_true",
        help="Enable VAD filter for long audios",
    )
    parser.add_argument(
        "--tmp-audio-path",
        type=Path,
        help="Optional temporary WAV path",
    )
    parser.add_argument(
        "--keep-temp-audio",
        action="store_true",
        help="Keep temporary WAV file after transcription",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.input.exists():
        raise SystemExit(f"Input video not found: {args.input}")
    if args.beam_size <= 0:
        raise SystemExit("--beam-size must be > 0")

    if not has_audio_stream(args.input):
        print("[warn] No audio stream found in video. Skipping transcription.")
        return 2

    try:
        from faster_whisper import WhisperModel
    except Exception as exc:
        print(
            "[error] faster-whisper is not installed.\n"
            "Install with: python3 -m pip install --upgrade faster-whisper",
            file=sys.stderr,
        )
        raise SystemExit(4) from exc

    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wav_path = args.tmp_audio_path or output_path.with_suffix(".wav")

    try:
        extract_audio_wav(args.input, wav_path)

        model = WhisperModel(
            args.model_size,
            device=args.device,
            compute_type=args.compute_type,
        )
        segments_iter, info = model.transcribe(
            str(wav_path),
            language=args.language,
            beam_size=args.beam_size,
            vad_filter=args.vad_filter,
        )
        segments = list(segments_iter)
        transcript = " ".join(seg.text.strip() for seg in segments if seg.text.strip()).strip()
        output_path.write_text((transcript + "\n") if transcript else "", encoding="utf-8")

        if args.segments_json:
            payload: dict[str, Any] = {
                "model_size": args.model_size,
                "language": getattr(info, "language", None),
                "language_probability": getattr(info, "language_probability", None),
                "segments": [
                    {
                        "index": i + 1,
                        "start_s": float(seg.start),
                        "end_s": float(seg.end),
                        "start_hhmmss": hhmmss(float(seg.start)),
                        "end_hhmmss": hhmmss(float(seg.end)),
                        "text": seg.text.strip(),
                    }
                    for i, seg in enumerate(segments)
                ],
            }
            args.segments_json.parent.mkdir(parents=True, exist_ok=True)
            args.segments_json.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        print(f"[ok] Transcript: {output_path}")
        return 0
    finally:
        if not args.keep_temp_audio and wav_path.exists():
            wav_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
