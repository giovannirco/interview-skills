---
name: interview-transcribe
description: >
  Turn an interview or meeting recording into a local, speaker-labelled transcript.
  Accepts any recording ffmpeg can read: phone voice memos (.m4a), OBS videos
  (.mkv/.mp4/.mov, single or multi-track audio), Zoom/Meet/Teams recordings,
  QuickTime screen recordings, plain audio. Extracts mono 16 kHz audio, runs Whisper
  large-v3-turbo locally (mlx-whisper on Apple Silicon, faster-whisper elsewhere),
  diarizes (pyannote community-1 with a Hugging Face token, else ECAPA + spectral
  clustering), names the speakers, and writes diarized + merged Markdown. Use after
  recording an interview, or when the user says "transcribe this interview",
  "diarize", "who said what", or /interview-transcribe.
---

# Interview transcribe + diarize

## Goal

Recording in → two Markdown transcripts out, every line labelled with a real name and a
timestamp, filed under `$INTERVIEWS_DIR/<company>-<role>/meetings/`. The audio never
leaves the machine and never goes into git.

Defaults (override with env vars):

| Var | Default | What |
|-----|---------|------|
| `INTERVIEWS_DIR` | `~/interviews` | Where interview folders live |
| `INTERVIEW_TRANSCRIBE_VENV` | `~/.interview-transcribe/venv` | Python env (see repo `SETUP.md`) |

The script is `scripts/transcribe_interview.py` in this skill's directory.

## Hard rules

1. **Never commit** recordings or extracted audio (`.mov .mp4 .mkv .m4a .wav …`). Work in a
   scratch dir.
2. **Never upload interview audio** to a cloud service unless the user explicitly asks.
3. Final transcripts carry **the names of the people who actually spoke**, not `SPEAKER_00`.
4. **Spot-check before trusting labels**: start / middle / end.
5. Fix systematic mishearings (company, people, products, tools) in the merged file; flag
   what's still uncertain instead of guessing.
6. File naming in `meetings/`:
   - `interview-N-<who>-transcript-diarized.md` — timestamps, speaker map, QA notes
   - `interview-N-<who>-transcript-merged.md` — **the analysis source of truth**

## Step 0 — environment check (first use in a session)

```bash
PY="${INTERVIEW_TRANSCRIBE_VENV:-$HOME/.interview-transcribe/venv}/bin/python"
command -v ffmpeg ffprobe && "$PY" -c "import torch, speechbrain, sklearn, soundfile; print('ok')"
ls ~/.cache/huggingface/token 2>/dev/null && echo "HF token present (pyannote path)" || echo "no HF token (spectral fallback)"
```

If anything is missing, walk the user through the repo's `SETUP.md` — don't improvise
installs.

## Step 1 — identify the recording and ask the essentials

Find it if the user didn't give a path:

```bash
ls -lht ~/Downloads ~/Movies ~/Desktop 2>/dev/null | grep -iE '\.(mov|mp4|mkv|m4a|mp3|wav|aac|caf|webm)$' | head
```

Inspect it — this tells you which recording type you have:

```bash
ffprobe -v error -show_entries format=duration:stream=index,codec_type,codec_name,channels:stream_tags=title -of compact "$SRC"
```

Ask the user (skip what they already said):

- Company + role (folder slug) and round number
- **Who actually spoke**, with roles: candidate / recruiter / hiring manager / engineer…
  (people on the invite who stayed silent don't count)
- Language, and names/tools Whisper is likely to mishear

### Recording types

| Source | What you'll see | How to handle |
|--------|-----------------|---------------|
| **iPhone Voice Memos / phone recorder** | `.m4a` (AAC, mono, 48 kHz) | Direct. Candidate is near-field, panel comes through a speaker — see "Phone / in-room" below |
| **OBS** | `.mkv` / `.mp4` / `.mov`, video + 1 or more audio tracks | Script lists tracks. Default **mixes all tracks**. If track 1 is already the full mix (common OBS setup: Track 1 = everything, Track 2 = mic), use `--audio-track 1` to avoid doubling the voices |
| **OBS with mic and desktop on separate tracks** | e.g. track 1 "Mic", track 2 "Desktop" | Mix (default) for the full transcript. To transcribe only the interviewers, `--audio-track 2` |
| **Zoom local recording** | folder with `.mp4` + `audio_only.m4a` (+ per-participant `.m4a` files if "separate audio file for each participant" was on) | Use `audio_only.m4a`. Per-participant files are the most reliable labels: transcribe each with `--num-speakers 1` if diarization struggles |
| **Google Meet / Teams cloud recording** | `.mp4` downloaded from Drive/Stream | Direct. Remote mono mix — pyannote strongly preferred |
| **QuickTime screen recording** | `.mov` | Check `ffprobe` shows an audio stream. QuickTime doesn't record system audio by default — the other side may be missing entirely. If so, tell the user; nothing can recover it |
| **Already a 16 kHz mono WAV** | `.wav` | Used as-is |

## Step 2 — run the pipeline

The script extracts audio itself (into `OUT_DIR/audio-mono-16k.wav`), so pass the original
recording.

```bash
PY="${INTERVIEW_TRANSCRIBE_VENV:-$HOME/.interview-transcribe/venv}/bin/python"
SCRIPT="<this skill dir>/scripts/transcribe_interview.py"
OUT="${TMPDIR:-/tmp}/interview-transcribe/$(date +%Y%m%d-%H%M%S)"

"$PY" "$SCRIPT" "$SRC" "$OUT" \
  --speakers "Alex:candidate,Sam:recruiter,Jordan:hm" \
  --num-speakers 3 \
  --title "Interview 2 — Acme"
```

Options:

| Flag | Use |
|------|-----|
| `--speakers "Name:role,…"` | Names for the clusters. Roles: `candidate`, `recruiter`, `hm`. Role tags let content cues pick the cluster ("next steps in the process" → recruiter, "on my team" → hiring manager, "I built…" → candidate); untagged names go by talk time. A **hint** — verify |
| `--num-speakers N` | People who **actually talked**. Defaults to the number of names |
| `--auto-count` | Let pyannote pick the count. Run it when unsure and compare to the forced count |
| `--language pt` | Non-English or mixed calls. Whisper's auto-detect only listens to the first 30 s |
| `--initial-prompt "Acme, Priya, Kubernetes"` | Prime spellings of names and tools |
| `--audio-track auto\|mix\|N` | Which audio track(s) to use (see table above) |
| `--reuse-asr` | Same `OUT` dir: skip Whisper, redo only diarization + naming (fast; for trying speaker counts) |
| `--force-fallback` | Skip pyannote, use spectral clustering |
| `--asr-model small` | Quick smoke test with a small model (mlx: `mlx-community/whisper-small-mlx`) |

Runtime on an M-series MacBook: ~20 s of ASR per 25 min of audio, plus ~30 s–2 min of
diarization. First run downloads models (~1.5 GB Whisper, ~30 MB pyannote).

Outputs in `OUT`: `transcript-diarized.md`, `transcript-merged.md`, `audio-mono-16k.wav`,
`asr_raw.json`, `diarization_turns.json`, `segments_labeled.json`, `speaker_map.json`,
`stats.json` (talk seconds per person).

## Step 3 — QA (required, with the user)

1. Show the user the speaker map and talk times from `stats.json`.
2. Pick three turns (start / middle / end) and have the user listen:
   `ffplay -nodisp -autoexit -ss <start_seconds> -t 15 "$OUT/audio-mono-16k.wav"`
   (or `afplay` after trimming). Confirm each label.
3. If labels are swapped: fix the names in both files (search/replace the name, keep
   timestamps). If two people are merged into one: re-run with `--reuse-asr` and a different
   `--num-speakers`, or `--auto-count`, or `--force-fallback` — compare.
4. Fix systematic mishearings (people, company, tools) in the merged file.
5. Collapse Whisper repeat-loops on silence/noise (the same word 20+ times) and note it in
   the diarized file's QA section.

## Step 4 — file it

```bash
MEET="${INTERVIEWS_DIR:-$HOME/interviews}/<company>-<role>/meetings"
mkdir -p "$MEET"
cp "$OUT/transcript-diarized.md" "$MEET/interview-N-<who>-transcript-diarized.md"
cp "$OUT/transcript-merged.md"   "$MEET/interview-N-<who>-transcript-merged.md"
```

If `$INTERVIEWS_DIR` is a git repo, make sure its `.gitignore` excludes media
(`*.mov *.mp4 *.mkv *.m4a *.wav *.mp3 *.webm`) and commit only the Markdown:
`interview(<company>): round N transcript`.

Then hand off to the `interview-process` skill (notes, review, status) — written from the
**merged** transcript. Delete the scratch `OUT` dir when the user is done with it.

## Phone / in-room recordings

A phone on the desk records the candidate loud and close, and the panel quiet and through a
laptop speaker. Lessons from a 69-minute, 6-invite panel recorded on an iPhone:

- Forcing `--num-speakers` to the invite count (6) **split the candidate into three
  clusters**; two invitees never spoke. Use the count that actually spoke — and run
  `--auto-count` too (both found 4).
- Map names by **content**, not talk time: whoever runs the agenda is the host; explicit
  handoffs ("Priya, do you want to take it from here?") name the next speaker; whoever pitches
  the role is usually the hiring manager. Check the map against ~20 turns where content makes
  the speaker certain.
- The near-field speaker's talk share is inflated — read it as an upper bound.
- Whisper invents repeat loops on non-speech and mishears names and acronyms ("SRE" → "CRE").

## Why this stack

Measured on a 24-minute, 3-person remote video call (candidate, recruiter, hiring manager),
against a hand-corrected transcript:

| Diarization | Accuracy | Note |
|-------------|----------|------|
| pyannote community-1 **exclusive** | **95.9%** (worst speaker 93.8%) | Preferred. ~29 s on Apple MPS |
| ECAPA on ASR segments + **spectral** clustering | **~93%**, balanced | Fallback, no token needed |
| NVIDIA Nemotron 3 Diarization | 92.6%, recruiter only 79% | Better on 6-person rooms, not 2–3 person calls |
| Windowed ECAPA + agglomerative | ~77%, recruiter **16%** | Merges remote voices — avoid |
| whisper.cpp tinydiarize | unusable | Never |

More in `references/stack-notes.md` and `references/notsofar-6spk.md`.

## Speaker naming cues

| Cue | Likely role |
|-----|-------------|
| Explains the process, "next steps", scheduling, "we'll be in touch" | Recruiter / TA |
| "Tell me…", team and roadmap talk, "on my team" | Hiring manager / eng lead |
| "I built", "in my current role", personal stories, the candidate's employers | Candidate |

## Optional: live captions

`scripts/live_transcribe.py` (Apple Silicon; `pip install sounddevice`) prints rolling
8-second transcripts from the microphone. No speaker labels. Only where transcription is
allowed.

## Related

- Skill `interview-process` — what to do with the transcript
- Repo `docs/career-ops-integration.md` — feeding transcripts into career-ops
