#!/usr/bin/env python3
"""Extract audio from video and transcribe via OpenAI-compatible API."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.error
import urllib.request
import uuid
from pathlib import Path

DEFAULT_ENV_FILE = Path("/home/marcelo/EvoGuia/.env.local")


def parse_dotenv_line(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[len("export ") :].strip()
    if "=" not in line:
        return None

    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None

    if value and value[0] in ("'", '"') and value[-1] == value[0]:
        value = value[1:-1]
    elif " #" in value:
        value = value.split(" #", 1)[0].rstrip()

    return key, value


def load_env_file(path: Path) -> bool:
    if not path.exists():
        return False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        parsed = parse_dotenv_line(raw_line)
        if not parsed:
            continue
        key, value = parsed
        if key not in os.environ:
            os.environ[key] = value
    return True


def resolve_gemini_api_key(env_file: Path | None) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        return api_key

    candidates: list[Path] = []
    if env_file is not None:
        candidates.append(env_file)
    candidates.append(DEFAULT_ENV_FILE)

    for candidate in candidates:
        loaded = load_env_file(candidate)
        if loaded and os.getenv("GEMINI_API_KEY"):
            print(f"[info] GEMINI_API_KEY loaded from {candidate}")
            return os.environ["GEMINI_API_KEY"]

    checked = ", ".join(str(p) for p in candidates)
    raise SystemExit(
        "GEMINI_API_KEY is required. Set env var or add it to .env.local. "
        f"Checked: {checked}"
    )


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


def extract_audio(video_path: Path, audio_path: Path, audio_format: str) -> None:
    codec_args: list[str]
    if audio_format == "mp3":
        codec_args = ["-c:a", "mp3", "-b:a", "64k"]
    else:
        codec_args = ["-c:a", "pcm_s16le"]

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
        *codec_args,
        str(audio_path),
    ]
    try:
        run_cmd(cmd)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found. Install ffmpeg package first.")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"ffmpeg audio extraction failed: {exc.stderr.strip()}") from exc


def content_type_for_audio(audio_format: str) -> str:
    if audio_format == "mp3":
        return "audio/mpeg"
    return "audio/wav"


def build_multipart_body(
    *,
    fields: dict[str, str],
    file_field_name: str,
    file_name: str,
    file_bytes: bytes,
    file_content_type: str,
) -> tuple[bytes, str]:
    boundary = "----videostand-" + uuid.uuid4().hex
    chunks: list[bytes] = []

    for key, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode(
                "utf-8"
            )
        )

    chunks.append(f"--{boundary}\r\n".encode("utf-8"))
    chunks.append(
        (
            f'Content-Disposition: form-data; name="{file_field_name}"; '
            f'filename="{file_name}"\r\n'
            f"Content-Type: {file_content_type}\r\n\r\n"
        ).encode("utf-8")
    )
    chunks.append(file_bytes)
    chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))

    body = b"".join(chunks)
    content_type = f"multipart/form-data; boundary={boundary}"
    return body, content_type


def call_transcriptions_api(
    *,
    api_base: str,
    api_key: str,
    model: str,
    audio_path: Path,
    language: str | None,
    prompt: str | None,
    timeout_seconds: int,
    audio_content_type: str,
) -> str:
    fields: dict[str, str] = {
        "model": model,
        "response_format": "json",
    }
    if language:
        fields["language"] = language
    if prompt:
        fields["prompt"] = prompt

    body, content_type = build_multipart_body(
        fields=fields,
        file_field_name="file",
        file_name=audio_path.name,
        file_bytes=audio_path.read_bytes(),
        file_content_type=audio_content_type,
    )

    url = api_base.rstrip("/") + "/audio/transcriptions"
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", content_type)

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read().decode("utf-8")
            obj = json.loads(raw)
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from transcription API: {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error calling transcription API: {exc}") from exc

    text = obj.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    raise RuntimeError("Transcription API response did not include text.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract audio from .mp4 and transcribe with OpenAI-compatible API."
    )
    parser.add_argument("--input", required=True, type=Path, help="Input video file")
    parser.add_argument("--output", required=True, type=Path, help="Output transcript text file")
    parser.add_argument("--model", default="gpt-4o-mini-transcribe", help="Transcription model")
    parser.add_argument("--api-base", default="https://api.openai.com/v1", help="API base URL")
    parser.add_argument("--language", default="pt", help="Audio language hint")
    parser.add_argument("--prompt", help="Optional prompt to guide transcription")
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Optional dotenv file used when GEMINI_API_KEY is not already set",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=300,
        help="HTTP timeout for transcription request",
    )
    parser.add_argument(
        "--tmp-audio-path",
        type=Path,
        help="Optional temporary extracted-audio path",
    )
    parser.add_argument(
        "--temp-audio-format",
        choices=["mp3", "wav"],
        default="mp3",
        help="Temporary extracted audio format (mp3 is faster for upload)",
    )
    parser.add_argument(
        "--keep-temp-audio",
        action="store_true",
        help="Keep temporary extracted audio file after transcription",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.input.exists():
        raise SystemExit(f"Input video not found: {args.input}")

    api_key = resolve_gemini_api_key(args.env_file)

    if not has_audio_stream(args.input):
        print("[warn] No audio stream found in video. Skipping transcription.")
        return 2

    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    temp_suffix = ".mp3" if args.temp_audio_format == "mp3" else ".wav"
    wav_path = args.tmp_audio_path or output_path.with_suffix(temp_suffix)
    audio_content_type = content_type_for_audio(args.temp_audio_format)
    try:
        extract_audio(args.input, wav_path, args.temp_audio_format)
        transcript = call_transcriptions_api(
            api_base=args.api_base,
            api_key=api_key,
            model=args.model,
            audio_path=wav_path,
            language=args.language,
            prompt=args.prompt,
            timeout_seconds=args.timeout_seconds,
            audio_content_type=audio_content_type,
        )
        output_path.write_text(transcript + "\n", encoding="utf-8")
        print(f"[ok] Transcript: {output_path}")
        return 0
    finally:
        if not args.keep_temp_audio and wav_path.exists():
            wav_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
