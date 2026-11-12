# interview-skills

Agent skills for job interviews: turn any interview recording into a **local,
speaker-labelled transcript**, and run each interview loop as an organised folder you can
learn from.

- Works with any agent harness that reads [Agent Skills](https://agentskills.io) (`SKILL.md`
  folders): Claude Code, OpenAI Codex CLI, Grok Build, and others — or just point any coding
  agent at a `SKILL.md`.
- Takes whatever you recorded: phone voice memo, OBS video (single or multi-track), Zoom /
  Meet / Teams recording, QuickTime, plain audio.
- Runs **fully offline** after the first model download. Your interview audio is never uploaded.
- Fastest on Apple Silicon Macs (mlx-whisper, the tested path); also set up for Linux and
  Windows (faster-whisper, CUDA or CPU).

```
skills/
├── interview-transcribe/        recording → "who said what" transcript
│   ├── SKILL.md                 the procedure the agent follows
│   ├── scripts/transcribe_interview.py
│   ├── scripts/live_transcribe.py   (optional live captions, Apple Silicon)
│   └── references/              benchmarks: why this model stack
└── interview-process/           how to run a whole interview loop
    ├── SKILL.md
    └── references/lessons-from-a-6-round-loop.md
docs/career-ops-integration.md   optional: feed transcripts into career-ops
SETUP.md                         install steps (macOS / Linux / Windows, any harness)
requirements.txt
```

**Get started:** [SETUP.md](SETUP.md).

`requirements.txt` specifies minimum versions, not a reproducible lockfile. The
model benchmarks below describe the tested October environment. A fresh install
can resolve newer packages; run the setup smoke test before trusting it with an
interview, and save the resolved versions of a working environment.

---

## What the skills do

### `interview-transcribe` — recording → transcript

You give the agent a recording and say who was on the call. It produces two Markdown files
where every line has a name and a timestamp:

```markdown
**Sam** [0:00.00–0:07.52]
Hi, thanks for joining today. I'm the recruiter on the talent team...

**Alex** [0:08.12–0:17.58]
Thanks for having me. In my current role I built the deployment platform...

**Jordan** [0:18.22–0:28.44]
Great. I lead the platform group... Tell me, how did you decide what to automate first?
```

Under the hood (`scripts/transcribe_interview.py`):

1. **Read the recording.** `ffprobe` lists its audio tracks; `ffmpeg` extracts mono 16 kHz
   audio. Multi-track OBS files are mixed (or one track picked with `--audio-track`).
2. **Speech → text.** OpenAI **Whisper large-v3-turbo**, locally: `mlx-whisper` on Apple
   Silicon, `faster-whisper` elsewhere. Text with timestamps, but no idea who is talking.
3. **Who spoke when (diarization).** Groups the audio by voice:
   **pyannote community-1** if you set up a free Hugging Face token (~96% accurate in tests),
   otherwise **speechbrain voice embeddings + spectral clustering** (~93%). Output is anonymous:
   `SPEAKER_00`, `SPEAKER_01`…
4. **Join and name.** Each text segment gets the voice talking at that moment; consecutive lines
   from one person are merged. Clusters get names from your hints
   (`--speakers "Alex:candidate,Sam:recruiter,Jordan:hm"`), role phrases ("next steps in the
   process" → recruiter, "on my team" → hiring manager, "I built…" → candidate) and talk time.
5. **Write** `transcript-diarized.md` (timestamps, speaker map, QA checklist) and
   `transcript-merged.md` (the clean one you analyse), plus JSON so any step can be re-run alone
   (e.g. `--reuse-asr` to retry speaker counts without re-transcribing).

The `SKILL.md` wraps that with the parts a script can't do: asking who actually spoke (not who
was invited), recognising the recording type, the quirks of phone recordings, a required
**listen-to-three-clips check** with you before the names are trusted, fixing misheard names,
and filing the result in `~/interviews/<company>-<role>/meetings/`.

### `interview-process` — the whole interview loop

No code; a method the agent follows so nothing gets lost between rounds:

| When | What gets written |
|------|-------------------|
| First call booked | `~/interviews/<company>-<role>/` with `status.md` (timeline, stages, odds, email drafts) and `prep/interview-prep.md` (your stories mapped to the job, gaps, questions) |
| Before each round | A one-page brief on the interviewer: background, public work, what they'll care about, questions tailored to them |
| Same day | Notes + transcript (skill above) + a review: what went well, what didn't, signals, **talk ratio** |
| 1–3 days later | A "fair review" with a cool head, separating facts from guesses |
| Process ends | A retrospective across rounds: recurring weak spots, prep that was used or wasted, who advocated and who doubted |

It was distilled from a real six-round loop; the lessons are in
`skills/interview-process/references/`.

### Together

```
record ──► interview-transcribe ──► meetings/interview-N-…-transcript-merged.md
                                          │
          interview-process ◄─────────────┘   notes · review · fair review · status · retrospective
                                          │
          (optional) career-ops interview/debrief  →  question bank, story bank, practice
```

## Using it

In your agent, after [setup](SETUP.md):

> /interview-transcribe ~/Movies/2026-10-06 acme.mkv — round 2 at Acme, Platform Engineer.
> Speakers: me (Alex, candidate), Sam (recruiter), Jordan (hiring manager). English.

The agent inspects the file, runs the pipeline, shows the speaker map, asks you to confirm a
few clips, fixes names, and files the transcripts. Then:

> /interview-process write the same-day review for Acme round 2

Without skills support, say: *"Read `skills/interview-transcribe/SKILL.md` and follow it for
this recording."*

The script also works on its own:

```bash
~/.interview-transcribe/venv/bin/python skills/interview-transcribe/scripts/transcribe_interview.py \
  recording.m4a out/ --speakers "Alex:candidate,Sam:recruiter" --num-speakers 2
```

## Ground rules

- **Recording consent.** Some companies forbid recording or AI note-takers, and some places
  require everyone's consent. Ask, or don't record and write notes right after the call.
- **Transcripts are private.** They hold other people's names and words — keep them out of
  public repos (`.gitignore` the media and the interviews folder).
- **Auto-names are a guess.** Always do the three-clip check.

## Why these models

Measured on a real 24-minute, 3-person remote call against a hand-corrected transcript:
pyannote community-1 (exclusive mode) 95.9%, speechbrain + spectral 93%, NVIDIA Nemotron 3
92.6% (but only 79% on one speaker), a naive sliding-window approach 77% (one voice almost
entirely absorbed into another). Details: `skills/interview-transcribe/references/`.

## License

MIT
