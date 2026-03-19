#!/usr/bin/env python3
"""Extract representative frames from a video and build a manifest."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, text=True, capture_output=True)


def parse_fps(raw: str) -> float | None:
    if not raw:
        return None
    try:
        return float(Fraction(raw))
    except Exception:
        return None


def ffprobe_video_info(video_path: Path) -> tuple[float | None, float | None]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=r_frame_rate",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(video_path),
    ]
    result = run_cmd(cmd)
    data = json.loads(result.stdout)

    fps = None
    duration = None

    streams = data.get("streams", [])
    if streams:
        fps = parse_fps(streams[0].get("r_frame_rate", ""))

    fmt = data.get("format", {})
    if "duration" in fmt:
        try:
            duration = float(fmt["duration"])
        except Exception:
            duration = None

    return fps, duration


def hhmmss(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    seconds = max(0.0, seconds)
    total_ms = int(round(seconds * 1000))
    s, ms = divmod(total_ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def validate_args(args: argparse.Namespace) -> None:
    if args.every_n_frames is not None and args.every_n_frames <= 0:
        raise ValueError("--every-n-frames must be > 0")
    if args.interval_seconds is not None and args.interval_seconds <= 0:
        raise ValueError("--interval-seconds must be > 0")
    if args.max_frames is not None and args.max_frames <= 0:
        raise ValueError("--max-frames must be > 0")
    if args.jpeg_quality < 2 or args.jpeg_quality > 31:
        raise ValueError("--jpeg-quality must be between 2 and 31")
    if args.max_width is not None and args.max_width <= 0:
        raise ValueError("--max-width must be > 0")


def build_ffmpeg_command(args: argparse.Namespace, output_pattern: str) -> list[str]:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(args.input),
    ]

    if args.interval_seconds is not None:
        sampling_filter = f"fps=1/{args.interval_seconds}"
    else:
        sampling_filter = f"select=not(mod(n\\,{args.every_n_frames}))"

    filters = [sampling_filter]
    if args.max_width is not None:
        filters.append(f"scale=min(iw\\,{args.max_width}):-2")
    vf = ",".join(filters)

    cmd.extend(["-vf", vf, "-vsync", "vfr", "-q:v", str(args.jpeg_quality)])

    if args.max_frames is not None:
        cmd.extend(["-frames:v", str(args.max_frames)])

    cmd.append(output_pattern)
    return cmd


def estimate_timestamp(
    index_zero_based: int,
    *,
    fps: float | None,
    every_n_frames: int | None,
    interval_seconds: float | None,
) -> float | None:
    if interval_seconds is not None:
        return index_zero_based * interval_seconds
    if fps and every_n_frames:
        return (index_zero_based * every_n_frames) / fps
    return None


def build_manifest(
    *,
    args: argparse.Namespace,
    files: list[Path],
    fps: float | None,
    duration: float | None,
) -> dict[str, Any]:
    frames: list[dict[str, Any]] = []
    for i, frame_path in enumerate(files):
        ts_s = estimate_timestamp(
            i,
            fps=fps,
            every_n_frames=args.every_n_frames,
            interval_seconds=args.interval_seconds,
        )
        frames.append(
            {
                "index": i + 1,
                "file": str(frame_path),
                "timestamp_s_estimated": ts_s,
                "timestamp_hhmmss_estimated": hhmmss(ts_s),
                "estimated_source_frame": (
                    None
                    if args.interval_seconds is not None
                    else i * (args.every_n_frames or 0)
                ),
            }
        )

    if fps and args.every_n_frames:
        approx_hz = fps / args.every_n_frames
    elif args.interval_seconds:
        approx_hz = 1.0 / args.interval_seconds
    else:
        approx_hz = None

    manifest = {
        "input_video": str(Path(args.input).resolve()),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "sampling": {
            "mode": "interval-seconds"
            if args.interval_seconds is not None
            else "every-n-frames",
            "every_n_frames": args.every_n_frames,
            "interval_seconds": args.interval_seconds,
            "approx_sample_rate_hz": approx_hz,
        },
        "image_processing": {
            "jpeg_quality": args.jpeg_quality,
            "max_width": args.max_width,
        },
        "video_info": {
            "fps_estimated": fps,
            "duration_s": duration,
            "duration_hhmmss": hhmmss(duration),
        },
        "counts": {
            "frames_extracted": len(frames),
        },
        "frames": frames,
    }
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract sampled frames from a video and write a manifest JSON."
    )
    parser.add_argument("--input", required=True, type=Path, help="Input .mp4 file")
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory where frames and manifest are stored",
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--every-n-frames",
        type=int,
        default=15,
        help="Extract 1 frame every N source frames (default: 15)",
    )
    mode.add_argument(
        "--interval-seconds",
        type=float,
        help="Extract 1 frame every N seconds (preferred for long videos)",
    )

    parser.add_argument(
        "--max-frames",
        type=int,
        help="Limit extracted frames",
    )
    parser.add_argument(
        "--jpeg-quality",
        type=int,
        default=6,
        help="ffmpeg quality scale 2..31 (2=best, 31=worst)",
    )
    parser.add_argument(
        "--max-width",
        type=int,
        help="Optional frame resize max width in pixels (keeps aspect ratio)",
    )
    args = parser.parse_args()

    try:
        validate_args(args)
    except ValueError as exc:
        parser.error(str(exc))

    input_path = Path(args.input)
    if not input_path.exists():
        parser.error(f"Input file not found: {input_path}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_pattern = str(output_dir / "frame_%06d.jpg")

    try:
        fps, duration = ffprobe_video_info(input_path)
    except FileNotFoundError:
        parser.error("ffprobe not found. Install ffmpeg package first.")
    except subprocess.CalledProcessError as exc:
        parser.error(f"ffprobe failed: {exc.stderr.strip()}")

    ffmpeg_cmd = build_ffmpeg_command(args, output_pattern)
    try:
        run_cmd(ffmpeg_cmd)
    except FileNotFoundError:
        parser.error("ffmpeg not found. Install ffmpeg package first.")
    except subprocess.CalledProcessError as exc:
        parser.error(f"ffmpeg failed: {exc.stderr.strip()}")

    files = sorted(output_dir.glob("frame_*.jpg"))
    if not files:
        parser.error("No frames were extracted. Try another sampling strategy.")

    manifest = build_manifest(args=args, files=files, fps=fps, duration=duration)
    manifest_path = output_dir / "frames_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"[ok] Extracted {len(files)} frames")
    print(f"[ok] Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
