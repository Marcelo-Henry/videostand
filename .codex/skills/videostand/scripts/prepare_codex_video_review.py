#!/usr/bin/env python3
"""Prepare a local review pack for Codex to summarize video from keyframes + transcript."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a Codex review pack from frame manifest and optional transcript."
    )
    parser.add_argument("--manifest", required=True, type=Path, help="Path to frames_manifest.json")
    parser.add_argument("--output-dir", required=True, type=Path, help="Output directory")
    parser.add_argument("--output", type=Path, help="Output markdown review pack path")
    parser.add_argument(
        "--transcript-file",
        type=Path,
        help="Optional transcript text file",
    )
    parser.add_argument(
        "--max-keyframes",
        type=int,
        default=24,
        help="Maximum keyframes copied for review",
    )
    parser.add_argument(
        "--max-transcript-chars",
        type=int,
        default=25000,
        help="Maximum transcript chars copied to review pack",
    )
    return parser.parse_args()


def pick_uniform_indices(total: int, take: int) -> list[int]:
    if total <= 0:
        return []
    if take >= total:
        return list(range(total))
    if take <= 1:
        return [0]

    idx: list[int] = []
    for i in range(take):
        pos = round(i * (total - 1) / (take - 1))
        idx.append(pos)

    unique: list[int] = []
    seen = set()
    for v in idx:
        if v not in seen:
            seen.add(v)
            unique.append(v)
    return unique


def resolve_frame_path(raw: str, manifest_dir: Path) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    return (manifest_dir / p).resolve()


def read_transcript(path: Path | None, max_chars: int) -> str | None:
    if path is None or not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return None
    if max_chars > 0 and len(text) > max_chars:
        return text[:max_chars] + "\n\n[transcript truncated]"
    return text


def main() -> int:
    args = parse_args()
    if args.max_keyframes <= 0:
        raise SystemExit("--max-keyframes must be > 0")
    if not args.manifest.exists():
        raise SystemExit(f"Manifest not found: {args.manifest}")

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    frames = manifest.get("frames", [])
    if not isinstance(frames, list) or not frames:
        raise SystemExit("Manifest has no frames.")

    manifest_dir = args.manifest.parent
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    keyframes_dir = output_dir / "review_keyframes"
    keyframes_dir.mkdir(parents=True, exist_ok=True)

    output_path = args.output or (output_dir / "codex_review_pack.md")
    keyframes_json = output_dir / "review_keyframes.json"

    picked_indices = pick_uniform_indices(len(frames), args.max_keyframes)
    selected: list[dict[str, Any]] = []
    for n, idx in enumerate(picked_indices, start=1):
        frame = frames[idx]
        raw_path = frame.get("file")
        if not isinstance(raw_path, str) or not raw_path:
            continue
        source_path = resolve_frame_path(raw_path, manifest_dir)
        if not source_path.exists():
            continue

        dst_name = f"keyframe_{n:03d}{source_path.suffix.lower() or '.jpg'}"
        dst_path = keyframes_dir / dst_name
        shutil.copy2(source_path, dst_path)

        selected.append(
            {
                "order": n,
                "source_index": frame.get("index"),
                "source_frame_path": str(source_path),
                "review_frame_path": str(dst_path),
                "timestamp_s_estimated": frame.get("timestamp_s_estimated"),
                "timestamp_hhmmss_estimated": frame.get("timestamp_hhmmss_estimated"),
            }
        )

    transcript_text = read_transcript(args.transcript_file, args.max_transcript_chars)

    lines: list[str] = []
    lines.append("# Codex Review Pack")
    lines.append("")
    lines.append(f"- Generated at (UTC): {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- Source manifest: {args.manifest.resolve()}")
    lines.append(f"- Total sampled frames: {len(frames)}")
    lines.append(f"- Keyframes selected: {len(selected)}")
    lines.append(f"- Transcript included: {'yes' if transcript_text else 'no'}")
    lines.append("")
    lines.append("## Keyframes")
    lines.append("")
    lines.append("Analyze these files directly with image tooling and build timeline from them.")
    lines.append("")

    for item in selected:
        ts = item.get("timestamp_hhmmss_estimated") or "unknown-time"
        lines.append(
            f"- {ts} | order={item['order']} | {item['review_frame_path']}"
        )

    lines.append("")
    lines.append("## Transcript")
    lines.append("")
    if transcript_text:
        lines.append("```text")
        lines.append(transcript_text)
        lines.append("```")
    else:
        lines.append("(not available)")
    lines.append("")

    output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    keyframes_json.write_text(
        json.dumps({"selected_keyframes": selected}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"[ok] Review pack: {output_path}")
    print(f"[ok] Keyframes JSON: {keyframes_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
