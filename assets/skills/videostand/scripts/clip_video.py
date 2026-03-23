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
    parser.add_argument("--vertical", action="store_true", help="Crop to vertical 9:16 aspect ratio (center-crop)")
    return parser.parse_args()

def get_video_info(input_path):
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "json", str(input_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    data = json.loads(result.stdout)
    return data["streams"][0]

def main():
    args = parse_args()
    
    if not args.input.exists():
        print(f"Error: Input file {args.input} does not exist.", file=sys.stderr)
        return 1

    # Base command
    cmd = ["ffmpeg", "-y", "-ss", str(args.start)]
    
    if args.end:
        cmd.extend(["-to", str(args.end)])
    elif args.duration:
        cmd.extend(["-t", str(args.duration)])
    
    cmd.extend(["-i", str(args.input)])

    if args.vertical:
        info = get_video_info(args.input)
        if info:
            w, h = int(info["width"]), int(info["height"])
            # Target 9:16 based on height
            target_w = int(h * 9 / 16)
            if target_w > w:
                target_w = w
                target_h = int(w * 16 / 9)
            else:
                target_h = h
            
            # Crop to target_w:target_h center
            crop_filter = f"crop={target_w}:{target_h}:(in_w-{target_w})/2:(in_h-{target_h})/2"
            cmd.extend(["-vf", crop_filter])
            # Re-encoding is required for filtering
            cmd.extend(["-c:v", "libx264", "-crf", "23", "-c:a", "aac", "-b:a", "128k"])
        else:
            print("Warning: Could not determine video dimensions, skipping vertical crop.", file=sys.stderr)
            cmd.extend(["-c", "copy"])
    else:
        # If no filtering, copy streams for speed
        cmd.extend(["-c", "copy"])

    cmd.append(str(args.output))

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print(f"[ok] Clip saved to {args.output}")
        return 0
    else:
        print(f"Error: ffmpeg failed with return code {result.returncode}", file=sys.stderr)
        return result.returncode

if __name__ == "__main__":
    sys.exit(main())
