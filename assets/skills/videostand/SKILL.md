---
name: videostand
description: Summarize local videos (.mp4) or YouTube links in local-first mode, without relying on external LLM APIs for image/audio understanding. Use when the agent receives a video, YouTube URL, or when the user requests a summary/timeline of screen recordings, gameplay, or vignettes. The main workflow uses frames + local transcription (faster-whisper) and the agent's own AI to interpret the keyframes.
---

# VideoStand

Extract representative frames, transcribe audio locally when available, and prepare a review package for the agent's AI to generate the final summary.

Prioritize time-based sampling (`--interval-seconds`) for long videos. Use `--every-n-frames` when frame-level granularity is required.

## When to Use

Use when the request involves:
- Summary of screen recordings, classes, gameplay, calls, interviews, or video demos;
- Timeline of events with approximate timestamps;
- Extraction of visual + contextual insights from transcribed audio;
- Identification of viral moments for short clips (TikTok, Reels, Shorts).

## When NOT to Use

Do not use this skill for:
- Video editing (cuts, overlays, color grading) — for merging multiple videos, see the **Merge Videos** section below;
- Legal transcription requiring word-for-word precision;
- High-risk inferences without primary source confirmation.

## Output Contract

Final response to the user should follow this adaptive order:
1. Executive Summary (3 to 6 lines)
2. Timeline (bullets with approximate time)
3. Viral Clip Suggestions (timestamps and reasoning) -> **Only if relevant/requested**.
4. Key Insights (or Technical Analysis if it's a bug/demo)
5. Understanding Limits (what could not be confirmed)

Rule: Maintain focus on practical utility and transparency about limits.

## Quick Start

Define the skill path (adjust target based on the agent used: `.codex`, `.kiro`, `.claude`...):

```bash
# Codex / Kiro
export VSUM="<skill-install-path>/scripts"

# Claude Code: use built-in variable
# ${CLAUDE_SKILL_DIR}/scripts
```

Execute full pipeline:

```bash
"$VSUM/run_video_summary.sh" ./video.mp4 ./output-video-summary gpt-4.1-mini
```

Or with YouTube URL:

```bash
"$VSUM/run_video_summary.sh" "https://www.youtube.com/watch?v=VIDEO_ID" ./output-video-summary gpt-4.1-mini
```

By default:
- Transcription: local (`faster-whisper`)
- Summary: local (`codex-local`, no API LLM call)

If `ffmpeg` is missing, the runner asks for permission to install automatically without exposing technical commands.
For YouTube links, `yt-dlp` must be installed.

Expected outputs:
- `output-video-summary/frames/*.jpg`
- `output-video-summary/frames/frames_manifest.json`
- `output-video-summary/audio_transcript.txt` (when audio exists)
- `output-video-summary/audio_transcript.segments.json` (when audio exists)
- `output-video-summary/review_keyframes/*.jpg`
- `output-video-summary/review_keyframes.json`
- `output-video-summary/codex_review_pack.md`

## Environment Doctor (recommended)

Before running analysis in a new environment, run a quick preflight:

```bash
"$VSUM/doctor.sh"
```

Strict mode (exit code 1 if mandatory dependency is missing):

```bash
"$VSUM/doctor.sh" --strict
```

Mandatory dependencies:
- `python3`
- `ffmpeg`
- `ffprobe`

Optional dependencies:
- `yt-dlp` (required for YouTube URLs only)
- `faster-whisper` (required for local audio transcription)

## Pre-Execution Planning (mandatory)

Before executing any command, the agent must build a 4-item micro-plan:
1. Request objective:
   - expected delivery type (short summary, timeline, insights).
2. Input type:
   - local file or URL, approximate duration, and signs of relevant audio.
3. Sampling strategy:
   - `--interval-seconds` for long videos; `--every-n-frames` for granularity.
4. Risks and fallback:
   - missing `ffmpeg`, `yt-dlp`, or local ASR, and how to respond while maintaining utility.

Rule: This planning should be short (maximum 6 mental lines) and must not be exposed as technical detail to the end user.

## Fast-Path Planning (fastest agent possible)

When speed is priority, the agent must follow this order:
1. Minimum validation:
   - confirm input exists and `ffmpeg/ffprobe` are available.
2. Fast pipeline:
   - `AUTO_SMART_SAMPLING=1`, `AUDIO_BACKEND=local`, `SUMMARY_BACKEND=codex-local`.
3. Cost reduction:
   - limit frames (`MAX_FRAMES`) and keyframes (`MAX_KEYFRAMES_FOR_REVIEW`) to accelerate.
4. Incremental delivery:
   - if audio is delayed/fails, deliver a useful visual summary first, then complement.
5. No unnecessary blocking:
   - avoid optional steps not requested by the user.

Rule: Prioritize total response time without compromising minimum summary quality.

## Output Policy (mandatory)

- Never reveal skill implementation details to the end user.
- Never respond with phrases like:
  - "I will use the skill..."
  - "I will extract frames..."
  - "I will call model X..."
  - technical logs, stack traces, script names, internal paths
- Deliver only:
  - what the video shows
  - timeline/insights/understanding limits
- If an internal technical error occurs, respond neutrally and result-oriented:
  - "I couldn't analyze this file right now. Please try again in a few moments."
  - "I only obtained visual analysis; audio was not understood."

## Permission Policy (ffmpeg)

- If `ffmpeg`/`ffprobe` are unavailable, ask for consent before installing.
- Mandatory message to the user:
  - "Can I install ffmpeg now? It will require administrator permission and may ask for your password."
- Do not show installation commands to the end user.
- Inform only that the installation will begin and that the system may open a permission/password prompt.
- Respect refusals: if the user denies, do not attempt to install and end with an objective message.

## Cleanup Policy (recommended)

- After producing the final summary for the user and ensuring delivery is complete, the agent must clean up heavy temporary files to save user disk space.
- Execute only if the summary was successfully generated.
- Command:
  ```bash
  "$VSUM/cleanup.sh" ./output-directory
- This action deletes frames, folders, and logs, keeping only the summary (.md) files.

## Workflow

1. Resolve input:
   - local file (`.mp4`)
   - YouTube URL (download to `output/input/` via `yt-dlp`)
2. Validate prerequisites (`ffmpeg`, `ffprobe`).
   - If `ffmpeg` is missing, follow `Permission Policy (ffmpeg)` before proceeding.
3. Extract frames:
   - by frame: `extract_frames.py --every-n-frames 15`
   - by time: `extract_frames.py --interval-seconds 0.5`
4. Generate `frames_manifest.json` with estimated timestamps.
5. Transcribe audio locally with `transcribe_audio_local.py` when an audio stream exists.
6. Prepare review keyframes + markdown package with `prepare_codex_video_review.py`.
7. Open `review_keyframes/*.jpg` and `codex_review_pack.md` within the agent itself.
8. **Person Framing Analysis** (mandatory when viral clips are requested): follow the section below.
9. Produce final summary for the user (without revealing backstage details).

## Person Framing Analysis (Smart Framing)

Before suggesting viral clips, the agent MUST analyze the framing of the person in the video to recommend the best vertical formatting mode.

### Sampling Strategy: 25 Frames in 5 Regions

The agent must extract and visually read **25 frames** distributed across 5 regions of the video:

| Region | Position in video                 | Frames                            |
| ------ | --------------------------------- | --------------------------------- |
| R1     | Beginning (0-10%)                 | 5 frames spaced within this range |
| R2     | Between start and middle (25-35%) | 5 spaced frames                   |
| R3     | Middle (45-55%)                   | 5 spaced frames                   |
| R4     | Between middle and end (65-75%)   | 5 spaced frames                   |
| R5     | End (90-100%)                     | 5 spaced frames                   |

To obtain these frames, the agent must use `extract_frames.py` with `--interval-seconds` calculated to capture frames in these regions, or use `ffmpeg` directly with `-ss` at specific timestamps.

### Visual Analysis of the 25 Frames

When reading the 25 frames, the agent must mentally answer:

1. **Is a person visible in most frames?** (>80% of frames = yes)
2. **Is the person consistently in the same horizontal position?**
   - Center: the person occupies the central strip of the frame
   - Center-left: between center and left
   - Center-right: between center and right
   - Left: the person is consistently on the left
   - Right: the person is consistently on the right
3. **Is the position stable across all 5 regions?**
   - If yes in at least 4 of 5 regions → consistent position confirmed
   - If no → variable position, use standard mode

### Two Vertical Formatting Modes

Based on the analysis:

| Analysis Result                           | Recommended Mode                                                            | `clip_video.py` Flag                      |
| ----------------------------------------- | --------------------------------------------------------------------------- | ----------------------------------------- |
| Person fixed in center                    | **Person Crop** — tight crop on the person, no blur, fills the whole screen | `--person-crop --person-position <pixel>` |
| Person fixed between center and left      | **Person Crop** adjusted for center-left                                    | `--person-crop --person-position <pixel>` |
| Person fixed on the left                  | **Person Crop** adjusted for left                                           | `--person-crop --person-position <pixel>` |
| Person fixed between center and right     | **Person Crop** adjusted for center-right                                   | `--person-crop --person-position <pixel>` |
| Person fixed on the right                 | **Person Crop** adjusted for right                                          | `--person-crop --person-position <pixel>` |
| Person moves / no person / dynamic camera | **Standard Mode** — centered horizontal video with blurred background       | `--vertical`                              |

Mandatory dynamic format for person-crop:
- `--person-position <pixel>`
- `<pixel>` is the X coordinate of the left edge of the crop in the original frame (0 = left edge).
- The script automatically clamps to respect original video horizontal boundaries.

### Presentation to the User

When the agent detects that person-crop is viable, it should include in the viral cuts proposal:

> "I've identified that you consistently appear centered in the video. I can create the cut focused on you (no side borders, you fill the whole screen) or in the standard format (original video in the center with blurred background). Which do you prefer?"

If the user doesn't choose, use **person-crop** as the default when analysis confirms a consistent position.

## Core Commands

Extract frames by time interval:

```bash
python3 "$VSUM/extract_frames.py" \
  --input ./video.mp4 \
  --output-dir ./tmp-frames \
  --interval-seconds 0.5 \
  --max-frames 180 \
  --max-width 960 \
  --jpeg-quality 6
```

Extract frames by frame skip:

```bash
python3 "$VSUM/extract_frames.py" \
  --input ./video.mp4 \
  --output-dir ./tmp-frames \
  --every-n-frames 15
```

Generate summary from manifest:

```bash
python3 "$VSUM/prepare_codex_video_review.py" \
  --manifest ./tmp-frames/frames_manifest.json \
  --output-dir ./tmp-frames \
  --max-keyframes 24 \
  --transcript-file ./tmp-frames/audio_transcript.txt \
  --output ./tmp-frames/codex_review_pack.md
```

Transcribe video audio:

```bash
python3 "$VSUM/transcribe_audio_local.py" \
  --input ./video.mp4 \
  --output ./tmp-frames/audio_transcript.txt \
  --segments-json ./tmp-frames/audio_transcript.segments.json \
  --model-size small \
  --language pt
```

Extract a cut with blurred background (standard mode):

```bash
python3 "$VSUM/clip_video.py" \
  --input ./video.mp4 \
  --output ./clip_viral_01.mp4 \
  --start 00:01:20 \
  --end 00:01:55 \
  --vertical  # 9:16 with blurred background
```

Extract a person-focused cut (person-crop):

```bash
python3 "$VSUM/clip_video.py" \
  --input ./video.mp4 \
  --output ./clip_viral_01.mp4 \
  --start 00:01:20 \
  --end 00:01:55 \
  --person-crop \
  --person-position 432  # <pixel> = left edge of crop; 0 = left edge of frame
```

Cleanup temporary files and logs (post-processing):

```bash
python3 "$VSUM/cleanup.sh" ./tmp-frames
```

## Performance Knobs

- `AUTO_SMART_SAMPLING=1` (default): automatically chooses `INTERVAL_SECONDS`, `MAX_FRAMES`, and `BATCH_SIZE` based on video duration.
- `AUDIO_BACKEND=local` (default): uses local transcription.
- `SUMMARY_BACKEND=codex-local` (default): prepares local pack for the agent's AI.
- `LOCAL_ASR_MODEL=small` (default): local Whisper model size.
- `MAX_KEYFRAMES_FOR_REVIEW=24` (default): quantity of keyframes for review.
- `MAX_WIDTH` and `JPEG_QUALITY`: control the size of sent frames.

Fast execution example:

```bash
AUTO_SMART_SAMPLING=1 \
AUDIO_BACKEND=local \
SUMMARY_BACKEND=codex-local \
MAX_WIDTH=960 \
MAX_KEYFRAMES_FOR_REVIEW=20 \
"$VSUM/run_video_summary.sh" ./video.mp4 ./output-fast gpt-4.1-mini
```

Install local ASR dependency:

```bash
"$VSUM/install_local_asr.sh"
```

## Quality Guardrails

- Avoid excessive frames in long videos. Use `--max-frames`.
- Prefer `--interval-seconds` in long recordings to reduce cost.
- Prioritize user-oriented final summary, without leaking execution details.
- Cite limits in the final summary:
  - without audio/transcription, understanding is visual only
  - timestamps are estimated when sampling by frame
- When valid audio is present, always combine image + transcription.

## Compatible API

API mode remains available only as an explicit fallback (`SUMMARY_BACKEND=api`, `AUDIO_BACKEND=api`).
Use only when explicitly requested by the user.

```bash
AUDIO_BACKEND=api \
SUMMARY_BACKEND=api \
"$VSUM/run_video_summary.sh" ./video.mp4 ./output-api gpt-4.1-mini
```

## Viral Video Strategy (Deep Specialization)

The agent is an **expert in identifying viral moments** with professional quality. When analyzing the `codex_review_pack.md` and transcript, the agent must find 1 to 5 moments with high engagement potential.

This analysis relies on **three mandatory pillars**:

### Pillar 1: Complete Reasoning (CRITICAL RULE — NEVER VIOLATE)

The agent **MUST NEVER** suggest a cut that interrupts a person's reasoning in the middle of an idea. This is the skill's most important rule.

**Completeness Rules:**
- Each cut MUST contain **beginning, development, and conclusion** of an idea or argument.
- The agent must read the transcript of the candidate segment and confirm that:
  - The person **introduces** the theme/idea at the beginning of the segment.
  - The person **develops** it with an explanation, example, or argument.
  - The person **concludes** with a closing statement, summary, or punchline.
- If a strong line of reasoning extends beyond 60 seconds, the agent **MUST propose the full segment**, even if it exceeds the "ideal duration." **Thought completeness > duration.**
- If there's no way to isolate a complete reasoning in under 90 seconds, the agent must inform the user and propose the entire segment.

**Signs of Incomplete Cut (FORBIDDEN):**
- Segment ends with hanging conjunctions: "...and...", "...but...", "...then...", "...because..."
- Segment ends with "...so what happens is..." or "...that's why I think..."
- Segment starts in the middle of an explanation without context
- The person is clearly building an argument that doesn't reach a conclusion in the cut
- The viewer would be left thinking "so what? what did they mean by that?"

> **ASR Margin (Safety Margin):** Audio transcription (Whisper) maps words, but the exact second limit in the log often cuts off the end of a breath or a person's last syllable. To avoid abrupt cuts, the agent **ALWAYS must add 2 to 3 seconds of padding** to the end timestamp (`--end`) of the chosen cut. If the transcript says the sentence ended at `00:01:20`, the cut command should go to `00:01:23`.
> **Start Margin:** Similarly, pull back 1 or 2 seconds from `--start` to avoid cutting the first syllable.

> **Practical Tip (Conjunctions):** If the ideal segment ends exactly at an "And..." or "But...", the agent must adjust the final timestamp (either backing up to cut BEFORE the conjunction or moving forward to include the entire following sentence).

### Pillar 2: High-Quality Speech Detection

The agent should prioritize segments where the person **speaks exceptionally well** on the topic. The items below are **indicators, not requirements** — a **single signal** is enough to mark the segment as high-quality speech. The more signals present, the stronger the segment:

- **Exceptional Clarity**: the person explains something complex in a simple, direct way.
- **Genuine Enthusiasm**: the energy in the speech increases, the person gets excited about the topic.
- **Strong Analogies**: the person uses comparisons that make the concept memorable.
- **Practical Examples**: the person illustrates with real cases (not every good segment has this — it's a bonus, not mandatory).
- **Quotable Sentences**: phrases that provide value on their own and are shareable.
  - Ex: "The secret is not working harder, it's eliminating what doesn't matter."
- **Conviction and Authority**: the person demonstrates mastery of the subject with confidence.

The agent should mark these segments with high priority in the proposal, using the `[STRONG SPEECH]` tag in the cut description.

### Pillar 3: Viral Potential (Engagement Hooks)

Criteria to identify viral potential in a segment:

- **Hook in the first 3 seconds**: impactful sentence, provocative question, controversial statement, or surprising visual action.
- **Revelation / Plot Twist**: an "aha moment" or unexpected revelation that changes perspective.
- **Punchline / Strong Conclusion**: the segment ends with impact — a memorable phrase, a laugh, a strong reaction.
- **Authentic Emotion**: surprise, indignation, humor, vulnerability — real reactions that connect.
- **Strong Contrast**: before/after, expectation/reality, myth/truth — the brain loves contrast.
- **Universality**: the theme resonates with many people, it's not too niche.

### Cut Duration

| Content Type           | Target Duration | Flexibility                                  |
| ---------------------- | --------------- | -------------------------------------------- |
| Quick hook / punchline | 15–30s          | Can be shorter if thought is complete        |
| Explanation / insight  | 30–60s          | Extend up to 90s if reasoning requires       |
| Deep reasoning / story | 60–120s         | NEVER cut to shorten; propose entire segment |

### Mandatory Viral Cuts Flow

If the user asks to generate viral cuts or best moments, the agent **MUST NOT** execute the cut immediately. The agent must follow this strict order:

1. **Person Framing Analysis**: Execute the 25-frame analysis (section above) to determine the best vertical formatting mode.
2. **Present the Proposal**: Show the user a numbered list with the identified cuts. For each cut, include:
   - **Period**: (Ex: `00:01:20 to 00:01:55`)
   - **Key Speech (Transcript)**: The key phrase(s) of the segment.
   - **Why it's a good cut**: Identify which pillar justifies it (complete reasoning, strong speech, viral hook).
   - **Tags**: `[COMPLETE REASONING]`, `[STRONG SPEECH]`, `[VIRAL HOOK]` — a cut can have multiple tags.
   - **Suggested Mode**: person-crop or vertical (based on framing analysis).
3. **Ask for Confirmation**: The agent should ask: "Would you like me to proceed with cutting and vertically formatting these segments? Note that this clipping process can be **time-consuming** as it involves video rendering."
4. **Quick Audio Validation (Mandatory Pre-Render)**: To avoid rendering an entire video in vain, before running `clip_video.py`, the agent MUST extract and transcribe just a quick audio snippet focusing on the first and last 5 seconds of the exact defined timestamps.
   - The agent can extract this audio using ffmpeg (e.g., separating just audio with `-ss` and `-to`).
   - If a sentence or reasoning break is detected (hanging syllable, hard cut):
   - The agent will **increase or decrease milliseconds or seconds** (`--start` or `--end`, using decimals, e.g., `00:01:20.500`) and test audio again until confirming the margin covers the entire speech cleanly.
   - The agent makes this fine-tuning on the current cut in the background without proposing a different cut or re-asking the user.
5. **Final Execution (Image Rendering)**: Only AFTER audio timestamps are perfectly validated will the agent use the long `clip_video.py` script with `--person-crop` or `--vertical` applying the corrected timestamps.

### Minimum Quality per Cut

Before including a cut in the proposal, the agent must go through this mental checklist:

- [ ] Does the segment contain a COMPLETE reasoning/idea? (beginning + development + conclusion)
- [ ] As a random viewer, would I understand the context without seeing the whole video?
- [ ] Does the segment have at least ONE strong hook (visual, verbal, or emotional)?
- [ ] Is the speech clear and articulate in this segment? (no excessive stuttering, no loss of focus)
- [ ] Is it worth sharing? Would someone send this to a friend?

If any item is "no," the agent must discard the segment or adjust timestamps to cover the complete reasoning.

## Critical Thinking in Analysis (Mental Model)

The agent must not be a passive transcription processor. It must apply a **critical thinking filter** before issuing any judgment or cut suggestions.

### 1. Objective Deconstruction
- **What does the author *think* they are saying vs. what they *are* saying?**
- Identify if the video is an attempt to "sell" an idea, a technical tutorial, or an emotional vent.
- The summary should reflect the **essence**, not just the word trail.

### 2. Validation of "Viral Moments"
- **Is the moment "Aha!" or just "Ok"?** If the agent is in doubt about whether a cut is good, it **is not good enough**. 
- A viral cut must resist the question: *"Would I stop scrolling for this?"*
- Avoid "filler" bias: it's better to propose 2 exceptional cuts than 5 mediocre ones.

### 3. Detection of Contradictions and Nuances
- If the person contradicts themselves or hesitates, that is an insight. Do not ignore flaws; they humanize the content and can be the best viral hooks.
- Critical thinking requires noticing what **was not said**: long silences, changes in voice tone, or facial expressions (via frames) that contradict the speech.

### 4. Intellectual Integrity Checklist
- [ ] Did I understand the macro context (who is the person, what is the purpose)?
- [ ] Am I suggesting the cut because it's *easy* to isolate or because it's *truly* valuable?
- [ ] Does the final summary add value to someone who *didn't* see the video?

## Technical Context Guardrails (Bug Reports)

If the video is clearly a technical screen recording (e.g., open browser console, IDE, code error, bug report, or software demo), the agent must:
- **Omit** viral cut suggestions (it would be inappropriate).
- **Focus** on identifying visual logs, error messages, and the exact flow that led to the problem.
- **Prioritize** the technical chronology of events over entertainment.

## Merge Videos

Use `merge_videos.py` when the user wants to join multiple video files into a single output. The agent has full control over the final order.

### When to Use

- User provides 2+ video files and asks to combine/join/merge them.
- User wants to reorder segments before merging (e.g. "put Z before X").
- User wants to concatenate clips produced by `clip_video.py`.

### Merge Command

```bash
python3 "$VSUM/merge_videos.py" \
  --inputs ./video_x.mp4 ./video_y.mp4 \
  --output ./merged.mp4
```

With custom order (0-based indices):

```bash
python3 "$VSUM/merge_videos.py" \
  --inputs ./video_x.mp4 ./video_y.mp4 ./video_z.mp4 \
  --order "2,0,1" \
  --output ./merged.mp4
```

Force re-encoding (different codecs or resolutions):

```bash
python3 "$VSUM/merge_videos.py" \
  --inputs ./video_x.mp4 ./video_y.mp4 \
  --reencode \
  --output ./merged.mp4
```

### Agent Workflow for Merge Requests

1. **List the inputs**: confirm each file exists before proceeding.
2. **Determine order**: if the user specifies an order, map it to `--order` indices. If not, use the order provided.
3. **Compatibility check**: the script auto-detects codec/resolution mismatches and switches to re-encoding automatically. Only pass `--reencode` explicitly if the user requests it.
4. **Execute**: run `merge_videos.py` and report the output path.
5. **Do not expose** script names, flags, or internal paths to the user.

### Output Policy

- Confirm success with the output file path.
- If the merge fails, respond neutrally: "I couldn't merge the videos right now. Please check that all files are valid and try again."

## References

- Base prompt and variations: `references/prompt_templates.md`
