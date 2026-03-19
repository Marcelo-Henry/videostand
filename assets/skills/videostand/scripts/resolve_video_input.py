#!/usr/bin/env python3
"""Resolve a local video path or download a YouTube URL to local .mp4."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from urllib.parse import urlparse


def is_youtube_url(raw: str) -> bool:
    try:
        parsed = urlparse(raw)
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.netloc.lower()
    return "youtube.com" in host or "youtu.be" in host


def find_downloaded_file(output_dir: Path, output_name: str) -> Path:
    candidates = sorted(output_dir.glob(f"{output_name}.*"))
    if not candidates:
        raise RuntimeError("yt-dlp did not produce a file in output directory.")

    for candidate in candidates:
        if candidate.suffix.lower() == ".mp4":
            return candidate.resolve()
    return candidates[-1].resolve()


def download_youtube(url: str, output_dir: Path, output_name: str) -> Path:
    if not shutil_which("yt-dlp"):
        raise RuntimeError(
            "yt-dlp is required for YouTube URLs. Install it and try again."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    out_template = output_dir / f"{output_name}.%(ext)s"
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--no-progress",
        "--restrict-filenames",
        "-f",
        "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best",
        "--merge-output-format",
        "mp4",
        "-o",
        str(out_template),
        url,
    ]
    try:
        subprocess.run(cmd, check=True, text=True, capture_output=True)
    except FileNotFoundError as exc:
        raise RuntimeError("yt-dlp is not installed.") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() or exc.stdout.strip()
        raise RuntimeError(f"yt-dlp failed: {stderr}") from exc

    return find_downloaded_file(output_dir, output_name)


def shutil_which(binary: str) -> str | None:
    # Keep this script dependency-light and compatible with old Python builds.
    from shutil import which

    return which(binary)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve local video path or download YouTube URL to local file."
    )
    parser.add_argument("--source", required=True, help="Local path or YouTube URL")
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory used when downloading from YouTube",
    )
    parser.add_argument(
        "--output-name",
        default="source_video",
        help="Base filename used for YouTube downloads",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.source.strip()
    maybe_local = Path(source)
    if maybe_local.exists():
        print(maybe_local.resolve())
        return 0

    if not is_youtube_url(source):
        raise SystemExit(
            "Input must be an existing local file or a valid YouTube URL "
            "(youtube.com / youtu.be)."
        )

    downloaded = download_youtube(source, args.output_dir, args.output_name)
    print(downloaded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
