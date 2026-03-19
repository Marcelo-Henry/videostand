#!/usr/bin/env python3
"""Summarize videos from sampled frames via an OpenAI-compatible Responses API."""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_SYSTEM_PROMPT = """You are a video analyst.
Infer the video progression only from provided sampled frames.
State uncertainty when information is missing.
Prefer concrete observations over speculation.
Return concise, high-signal output."""
DEFAULT_ENV_FILE = Path("/home/marcelo/EvoGuia/.env.local")


def encode_image_as_data_url(path: Path) -> str:
    suffix = path.suffix.lower()
    mime = "image/jpeg"
    if suffix == ".png":
        mime = "image/png"
    elif suffix == ".webp":
        mime = "image/webp"

    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def call_responses_api(
    *,
    api_base: str,
    api_key: str,
    payload: dict[str, Any],
    timeout_s: int,
) -> dict[str, Any]:
    url = api_base.rstrip("/") + "/responses"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from Responses API: {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error calling Responses API: {exc}") from exc


def extract_text(response: dict[str, Any]) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    texts: list[str] = []
    for item in response.get("output", []):
        for content in item.get("content", []):
            if isinstance(content, dict):
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    texts.append(text.strip())

    merged = "\n\n".join(texts).strip()
    if merged:
        return merged
    raise RuntimeError("Could not parse text output from Responses API response.")


def batched(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def timestamp_label(frame: dict[str, Any]) -> str:
    hhmm = frame.get("timestamp_hhmmss_estimated")
    if isinstance(hhmm, str) and hhmm:
        return hhmm
    sec = frame.get("timestamp_s_estimated")
    if isinstance(sec, (int, float)):
        return f"{sec:.3f}s"
    return "unknown-time"


def resolve_frame_path(frame: dict[str, Any], manifest_dir: Path) -> Path:
    raw = frame.get("file")
    if not isinstance(raw, str) or not raw:
        raise RuntimeError("Invalid frame entry in manifest: missing file path.")
    p = Path(raw)
    if not p.is_absolute():
        p = (manifest_dir / p).resolve()
    return p


def run_batch_summaries(
    *,
    frames: list[dict[str, Any]],
    args: argparse.Namespace,
    system_prompt: str,
    transcript_text: str | None,
    manifest_dir: Path,
    api_key: str,
) -> list[dict[str, Any]]:
    chunks = batched(frames, args.batch_size)
    partials: list[dict[str, Any]] = []
    chunk_transcript_text = None
    if transcript_text and args.chunk_transcript_chars > 0:
        if len(transcript_text) <= args.chunk_transcript_chars:
            chunk_transcript_text = transcript_text
        else:
            chunk_transcript_text = (
                transcript_text[: args.chunk_transcript_chars]
                + "\n\n[transcript context truncated for chunk step]"
            )

    def summarize_chunk(
        chunk_index: int,
        chunk: list[dict[str, Any]],
    ) -> dict[str, Any]:
        frame_lines: list[str] = []
        content: list[dict[str, Any]] = []
        content.append(
            {
                "type": "input_text",
                "text": (
                    f"Chunk {chunk_index}/{len(chunks)}. "
                    f"Language: {args.language}. "
                    "Analyze these frames as one contiguous segment. "
                    "Return: (1) what is happening, (2) key visual events with timestamps, "
                    "(3) uncertainty notes."
                ),
            }
        )
        if chunk_transcript_text:
            content.append(
                {
                    "type": "input_text",
                    "text": (
                        "Audio transcript context (may contain ASR errors; cross-check with visuals):\n"
                        f"{chunk_transcript_text}"
                    ),
                }
            )

        for frame in chunk:
            frame_path = resolve_frame_path(frame, manifest_dir)
            if not frame_path.exists():
                raise RuntimeError(f"Frame file not found: {frame_path}")

            frame_lines.append(
                f"- {timestamp_label(frame)} | {frame_path.name} | idx={frame.get('index')}"
            )
            content.append(
                {
                    "type": "input_image",
                    "image_url": encode_image_as_data_url(frame_path),
                    "detail": args.detail,
                }
            )

        content.insert(
            1,
            {
                "type": "input_text",
                "text": "Frame index map:\n" + "\n".join(frame_lines),
            },
        )

        payload = {
            "model": args.model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {"role": "user", "content": content},
            ],
            "max_output_tokens": args.batch_max_tokens,
        }
        response = call_responses_api(
            api_base=args.api_base,
            api_key=api_key,
            payload=payload,
            timeout_s=args.timeout_seconds,
        )
        text = extract_text(response)
        return {
            "chunk_index": chunk_index,
            "chunk_size": len(chunk),
            "summary": text,
        }

    if args.parallel_requests <= 1:
        for i, chunk in enumerate(chunks, start=1):
            partial = summarize_chunk(i, chunk)
            partials.append(partial)
            print(f"[ok] Chunk {i}/{len(chunks)} summarized ({len(chunk)} frames).")
    else:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=args.parallel_requests
        ) as executor:
            future_to_chunk = {
                executor.submit(summarize_chunk, i, chunk): (i, len(chunk))
                for i, chunk in enumerate(chunks, start=1)
            }
            for future in concurrent.futures.as_completed(future_to_chunk):
                chunk_index, chunk_size = future_to_chunk[future]
                partial = future.result()
                partials.append(partial)
                print(
                    f"[ok] Chunk {chunk_index}/{len(chunks)} summarized ({chunk_size} frames)."
                )

    partials.sort(key=lambda item: int(item["chunk_index"]))
    return partials


def build_final_summary(
    *,
    partials: list[dict[str, Any]],
    transcript_text: str | None,
    args: argparse.Namespace,
    system_prompt: str,
    api_key: str,
) -> str:
    chunks_text = []
    for p in partials:
        chunks_text.append(
            f"## Chunk {p['chunk_index']}\n"
            f"Frames: {p['chunk_size']}\n"
            f"{p['summary']}"
        )
    merged = "\n\n".join(chunks_text)

    final_prompt = (
        f"Language: {args.language}.\n"
        "You will receive partial summaries generated from sampled frames of one video"
        " and optional audio transcript context.\n"
        "Create the final output in markdown with sections:\n"
        "1) Resumo geral (3-6 bullets)\n"
        "2) Timeline estimada (timestamp + evento)\n"
        "3) Falas/Audio relevantes (se houver contexto suficiente)\n"
        "4) Insights praticos\n"
        "5) Limites e incertezas\n\n"
        f"Audio transcript context:\n{transcript_text or '(not provided)'}\n\n"
        "Partials:\n"
        f"{merged}"
    )

    payload = {
        "model": args.model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
            {"role": "user", "content": [{"type": "input_text", "text": final_prompt}]},
        ],
        "max_output_tokens": args.final_max_tokens,
    }
    response = call_responses_api(
        api_base=args.api_base,
        api_key=api_key,
        payload=payload,
        timeout_s=args.timeout_seconds,
    )
    return extract_text(response)


def read_prompt_file(path: Path | None) -> str:
    if path is None:
        return DEFAULT_SYSTEM_PROMPT
    if not path.exists():
        raise RuntimeError(f"Prompt file does not exist: {path}")
    return path.read_text(encoding="utf-8").strip() or DEFAULT_SYSTEM_PROMPT


def read_transcript_file(path: Path | None, max_chars: int) -> str | None:
    if path is None:
        return None
    if not path.exists():
        raise RuntimeError(f"Transcript file does not exist: {path}")
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return None
    if max_chars > 0 and len(text) > max_chars:
        return text[:max_chars] + "\n\n[transcript truncated]"
    return text


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

    checked: list[Path] = []
    candidates: list[Path] = []
    if env_file is not None:
        candidates.append(env_file)
    candidates.append(DEFAULT_ENV_FILE)

    for candidate in candidates:
        checked.append(candidate)
        loaded = load_env_file(candidate)
        if loaded and os.getenv("GEMINI_API_KEY"):
            print(f"[info] GEMINI_API_KEY loaded from {candidate}")
            return os.environ["GEMINI_API_KEY"]

    checked_text = ", ".join(str(p) for p in checked)
    raise SystemExit(
        "GEMINI_API_KEY is required. Set env var or add it to .env.local. "
        f"Checked: {checked_text}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize a video from extracted frame manifest via Responses API."
    )
    parser.add_argument("--manifest", required=True, type=Path, help="Path to frames_manifest.json")
    parser.add_argument("--model", default="gpt-4.1-mini", help="Vision-capable model name")
    parser.add_argument("--api-base", default="https://api.openai.com/v1", help="Responses API base URL")
    parser.add_argument("--batch-size", type=int, default=12, help="Frames per request")
    parser.add_argument("--max-frames", type=int, help="Cap frame count from manifest")
    parser.add_argument("--detail", choices=["low", "high", "auto"], default="low", help="Image detail mode")
    parser.add_argument("--language", default="pt-BR", help="Output language hint")
    parser.add_argument("--output", type=Path, help="Output markdown path")
    parser.add_argument("--prompt-file", type=Path, help="Optional system prompt file")
    parser.add_argument(
        "--transcript-file",
        type=Path,
        help="Optional transcript text file to enrich timeline understanding",
    )
    parser.add_argument(
        "--max-transcript-chars",
        type=int,
        default=12000,
        help="Maximum characters loaded from transcript file",
    )
    parser.add_argument(
        "--chunk-transcript-chars",
        type=int,
        default=1200,
        help="Transcript characters injected in each chunk request (0 disables)",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Optional dotenv file used when GEMINI_API_KEY is not already set",
    )
    parser.add_argument("--timeout-seconds", type=int, default=180, help="HTTP timeout")
    parser.add_argument(
        "--parallel-requests",
        type=int,
        default=2,
        help="Number of chunk requests sent in parallel",
    )
    parser.add_argument("--batch-max-tokens", type=int, default=900, help="Max tokens for each chunk")
    parser.add_argument("--final-max-tokens", type=int, default=1400, help="Max tokens for final merge")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be > 0")
    if args.max_frames is not None and args.max_frames <= 0:
        raise SystemExit("--max-frames must be > 0")
    if args.chunk_transcript_chars < 0:
        raise SystemExit("--chunk-transcript-chars must be >= 0")
    if args.parallel_requests <= 0:
        raise SystemExit("--parallel-requests must be > 0")

    api_key = resolve_gemini_api_key(args.env_file)

    if not args.manifest.exists():
        raise SystemExit(f"Manifest not found: {args.manifest}")

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    frames = manifest.get("frames", [])
    if not isinstance(frames, list) or not frames:
        raise SystemExit("Manifest has no frames.")

    if args.max_frames is not None:
        frames = frames[: args.max_frames]

    manifest_dir = args.manifest.parent
    output_path = args.output or (manifest_dir / "video_summary.md")
    partials_path = output_path.with_suffix(".partials.json")
    system_prompt = read_prompt_file(args.prompt_file)
    transcript_text = read_transcript_file(args.transcript_file, args.max_transcript_chars)

    print(f"[info] Frames to analyze: {len(frames)}")
    if transcript_text:
        print(f"[info] Transcript loaded ({len(transcript_text)} chars).")
    partials = run_batch_summaries(
        frames=frames,
        args=args,
        system_prompt=system_prompt,
        transcript_text=transcript_text,
        manifest_dir=manifest_dir,
        api_key=api_key,
    )
    final_summary = build_final_summary(
        partials=partials,
        transcript_text=transcript_text,
        args=args,
        system_prompt=system_prompt,
        api_key=api_key,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Video Summary\n\n"
        f"- Generated at (UTC): {datetime.now(timezone.utc).isoformat()}\n"
        f"- Model: {args.model}\n"
        f"- Frames analyzed: {len(frames)}\n"
        f"- Transcript used: {'yes' if transcript_text else 'no'}\n"
        f"- Source manifest: {args.manifest.resolve()}\n\n"
    )
    output_path.write_text(header + final_summary + "\n", encoding="utf-8")
    partials_path.write_text(json.dumps(partials, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[ok] Final summary: {output_path}")
    print(f"[ok] Partials JSON: {partials_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130)
