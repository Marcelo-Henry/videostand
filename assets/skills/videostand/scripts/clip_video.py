#!/usr/bin/env python3
"""Extract a clip from a video using ffmpeg."""

import argparse
import subprocess
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Extract a clip from a video.")
    parser.add_argument("--input", required=True, type=Path, help="Input video path")
    parser.add_argument("--output", required=True, type=Path, help="Output clip path")
    parser.add_argument("--start", required=True, help="Start time (HH:MM:SS or seconds)")
    parser.add_argument("--end", help="End time (HH:MM:SS or seconds)")
    parser.add_argument("--duration", help="Duration of the clip (seconds)")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--vertical", action="store_true",
        help="Format to vertical 9:16 (1080x1920 30fps) with blurred background",
    )
    mode.add_argument(
        "--person-crop", action="store_true",
        help="Tight vertical 9:16 crop centred on the person (no blur, full-frame person)",
    )

    parser.add_argument(
        "--person-position",
        type=int,
        metavar="PIXEL",
        help=(
            "Manual horizontal crop anchor for --person-crop. "
            "Format: --person-position <pixel>. "
            "PIXEL is always the left edge of the crop in the source frame."
        ),
    )
    args = parser.parse_args()

    if args.person_position is not None:
        if args.person_position < 0:
            parser.error("--person-position <pixel> must be >= 0.")

    return args


def get_video_info(input_path):
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "json", str(input_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    data = json.loads(result.stdout)
    return data["streams"][0]


def _build_person_crop_filter(w, h, position):
    """Build ffmpeg filter for a tight 9:16 crop around the person.

    Strategy: take a vertical slice from the original frame whose aspect
    ratio is 9:16. The slice width is ``h * 9 / 16`` (capped at ``w``).
    If *position* is provided, PIXEL is used as the left edge of the crop.
    If *position* is omitted, crop is centered.
    PIXEL is always interpreted in the source frame coordinate system,
    where x=0 is the left edge.
    The result is then scaled to exactly 1080x1920.
    """
    crop_w = min(int(h * 9 / 16), w)
    max_x = max(w - crop_w, 0)

    if position is None:
        x_val = (w - crop_w) // 2
    else:
        x_val = max(0, min(position, max_x))

    return f"crop={crop_w}:{h}:{x_val}:0,scale=1080:1920"


def main():
    args = parse_args()

    if not args.input.exists():
        print(f"Error: Input file {args.input} does not exist.", file=sys.stderr)
        return 1

    cmd = ["ffmpeg", "-y", "-ss", str(args.start)]

    if args.end:
        cmd.extend(["-to", str(args.end)])
    elif args.duration:
        cmd.extend(["-t", str(args.duration)])

    cmd.extend(["-i", str(args.input)])

    if args.vertical or args.person_crop:
        info = get_video_info(args.input)
        if info:
            w, h = int(info["width"]), int(info["height"])

            if args.person_crop:
                vf = _build_person_crop_filter(w, h, args.person_position)
                cmd.extend(["-vf", vf, "-map", "0:v", "-map", "0:a?"])
            else:
                filter_complex = (
                    "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
                    "crop=1080:1920,boxblur=20:20[bg];"
                    "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
                    "[bg][fg]overlay=(W-w)/2:(H-h)/2[outv]"
                )
                cmd.extend([
                    "-filter_complex", filter_complex,
                    "-map", "[outv]", "-map", "0:a?",
                ])

            cmd.extend([
                "-r", "30",
                "-c:v", "libx264", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
            ])
        else:
            print(
                "Warning: Could not determine video dimensions, skipping crop.",
                file=sys.stderr,
            )
            cmd.extend(["-c", "copy"])
    else:
        cmd.extend(["-c", "copy"])

    cmd.append(str(args.output))

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        print(f"[ok] Clip saved to {args.output}")
        return 0
    else:
        print(
            f"Error: ffmpeg failed with return code {result.returncode}",
            file=sys.stderr,
        )
        return result.returncode


if __name__ == "__main__":
    sys.exit(main())
