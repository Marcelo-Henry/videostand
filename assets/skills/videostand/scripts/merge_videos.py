#!/usr/bin/env python3
"""Merge multiple videos into a single file using ffmpeg."""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Merge multiple videos into one.")
    parser.add_argument(
        "--inputs", required=True, nargs="+", type=Path,
        help="Input video paths in desired order",
    )
    parser.add_argument("--output", required=True, type=Path, help="Output video path")
    parser.add_argument(
        "--order",
        help="Comma-separated 0-based indices to reorder inputs (e.g. '2,0,1')",
    )
    parser.add_argument(
        "--reencode", action="store_true",
        help="Force re-encoding (required when videos have different codecs/resolutions)",
    )
    return parser.parse_args()


def get_stream_info(path: Path) -> dict:
    """Return video stream info and whether an audio stream exists."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt",
        "-of", "json", str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return {"video": {}, "has_audio": False}
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    return {"video": video, "has_audio": has_audio}


def videos_are_compatible(infos: list[dict]) -> bool:
    """Check if all videos share the same codec, resolution, frame rate, and pixel format."""
    if not all(i["video"] for i in infos):
        return False
    codecs = {i["video"].get("codec_name") for i in infos}
    sizes = {(i["video"].get("width"), i["video"].get("height")) for i in infos}
    fps = {i["video"].get("r_frame_rate") for i in infos}
    pix_fmts = {i["video"].get("pix_fmt") for i in infos}
    return len(codecs) == 1 and len(sizes) == 1 and len(fps) == 1 and len(pix_fmts) == 1


def merge_concat_demuxer(paths: list[Path], output: Path) -> int:
    """Fast merge via concat demuxer (stream copy, no re-encoding)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for p in paths:
            escaped = str(p.resolve()).replace("'", "\\'")
            f.write(f"file '{escaped}'\n")
        list_file = f.name

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        str(output),
    ]
    print(f"[info] Merging {len(paths)} videos (stream copy)...")
    result = subprocess.run(cmd)
    Path(list_file).unlink(missing_ok=True)
    return result.returncode


def merge_concat_filter(paths: list[Path], output: Path, all_have_audio: bool) -> int:
    """Re-encoding merge via concat filter (handles different codecs/resolutions)."""
    cmd = ["ffmpeg", "-y"]
    for p in paths:
        cmd.extend(["-i", str(p)])

    n = len(paths)
    if all_have_audio:
        filter_parts = "".join(f"[{i}:v][{i}:a]" for i in range(n))
        filter_complex = f"{filter_parts}concat=n={n}:v=1:a=1[outv][outa]"
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
        ])
    else:
        filter_parts = "".join(f"[{i}:v]" for i in range(n))
        filter_complex = f"{filter_parts}concat=n={n}:v=1:a=0[outv]"
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-c:v", "libx264", "-crf", "23",
        ])

    cmd.append(str(output))
    print(f"[info] Merging {len(paths)} videos (re-encoding)...")
    result = subprocess.run(cmd)
    return result.returncode


def main():
    args = parse_args()

    # Validate inputs
    for p in args.inputs:
        if not p.exists():
            print(f"[error] Input file not found: {p}", file=sys.stderr)
            return 1

    # Apply custom order
    paths = list(args.inputs)
    if args.order:
        try:
            indices = [int(i.strip()) for i in args.order.split(",")]
            if sorted(indices) != list(range(len(paths))):
                print(
                    f"[error] --order must contain each index 0..{len(paths)-1} exactly once.",
                    file=sys.stderr,
                )
                return 1
            paths = [paths[i] for i in indices]
        except ValueError:
            print("[error] --order must be comma-separated integers (e.g. '2,0,1').", file=sys.stderr)
            return 1

    print("[info] Merge order:")
    for i, p in enumerate(paths):
        print(f"  {i + 1}. {p}")

    infos = [get_stream_info(p) for p in paths]
    all_have_audio = all(i["has_audio"] for i in infos)
    some_have_audio = any(i["has_audio"] for i in infos)
    if some_have_audio and not all_have_audio:
        print("[warn] Some inputs have no audio — merged output will have no audio track.", file=sys.stderr)

    args.output.parent.mkdir(parents=True, exist_ok=True)

    if args.reencode:
        rc = merge_concat_filter(paths, args.output, all_have_audio)
    else:
        if not videos_are_compatible(infos):
            print(
                "[warn] Videos have different codecs, resolutions, frame rates, or pixel formats. Switching to re-encoding mode.",
                file=sys.stderr,
            )
            rc = merge_concat_filter(paths, args.output, all_have_audio)
        else:
            rc = merge_concat_demuxer(paths, args.output)

    if rc == 0:
        print(f"[ok] Merged video saved to {args.output}")
    else:
        print(f"[error] ffmpeg failed with return code {rc}", file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
