# Setup

One-time, ~15 minutes (most of it downloads). Four parts:

1. System tools (`ffmpeg`, Python)
2. Python environment for the transcription script
3. Optional: Hugging Face token for the best speaker separation
4. Install the skills into your agent harness

Then a smoke test.

| Platform | Speech-to-text engine | Speed (25-min call) | Notes |
|----------|----------------------|---------------------|-------|
| **macOS 14+, Apple Silicon (M1–M5)** — preferred | `mlx-whisper` (GPU via Metal) | ~20–40 s | Best tested path |
| Linux / Windows with NVIDIA GPU | `faster-whisper` (CUDA) | ~30–60 s | |
| Linux / Windows, CPU only | `faster-whisper` (int8) | several minutes | Works; just slower |

The script picks the engine automatically. **Intel Macs are not supported**: current PyTorch
no longer ships macOS x86_64 builds (use a Linux/Windows machine instead).

Tested end to end on Apple Silicon. Linux and Windows dependency sets resolve, but no full
run was done on them yet — reports welcome.

---

## 1. System tools

You need **ffmpeg** (with `ffprobe`) and **Python 3.11–3.13**. `uv` is optional but makes the
next step faster.

**macOS** (Homebrew):

```bash
brew install ffmpeg python@3.13 uv
```

**Linux** (Debian/Ubuntu):

```bash
sudo apt install ffmpeg python3 python3-venv
curl -LsSf https://astral.sh/uv/install.sh | sh     # optional
```

**Windows**: easiest is **WSL2 (Ubuntu)** and the Linux steps. Native also works:

```powershell
winget install Gyan.FFmpeg Python.Python.3.13 astral-sh.uv
```

Check: `ffmpeg -version` and `python3 --version` (Windows: `python --version`).

## 2. Python environment

The skills expect the env at `~/.interview-transcribe/venv`. Put it elsewhere if you like and
set `INTERVIEW_TRANSCRIBE_VENV` to that path in your shell profile.

From this repo's root:

**With uv** (macOS / Linux / WSL):

```bash
uv venv --python 3.13 ~/.interview-transcribe/venv
uv pip install --python ~/.interview-transcribe/venv/bin/python -r requirements.txt
```

**With plain pip**:

```bash
python3 -m venv ~/.interview-transcribe/venv
~/.interview-transcribe/venv/bin/pip install -r requirements.txt
```

**Windows native**: the interpreter is `%USERPROFILE%\.interview-transcribe\venv\Scripts\python.exe`
instead of `…/bin/python`. Wherever the skills say `$VENV/bin/python`, the agent should use
that path.

`requirements.txt` installs `mlx-whisper` on Apple Silicon and `faster-whisper` everywhere
else, plus `torch`, `speechbrain`, `scikit-learn`, `soundfile` and `pyannote.audio`.

**NVIDIA GPU (Linux/Windows):** if `python -c "import torch; print(torch.cuda.is_available())"`
prints `False`, install the CUDA build of torch from https://pytorch.org/get-started/locally/
into the same venv. faster-whisper also needs cuDNN/cuBLAS — see its README.

Check:

```bash
~/.interview-transcribe/venv/bin/python -c "import torch, speechbrain, sklearn, soundfile, pyannote.audio; print('ok')"
```

The requirements are minimum versions, so this import check does not reproduce
the October benchmark or prove transcription and diarization work together.
After the end-to-end smoke test in step 6 passes, save the installed versions:

```bash
uv pip freeze --python ~/.interview-transcribe/venv/bin/python > ~/.interview-transcribe/requirements-working.txt
```

Keep that local snapshot with your environment notes. CLI help, audio extraction
and transcript formatting can pass even when the ASR or diarization models are
missing; verify those stages with a short recording before a real interview.

## 3. Hugging Face token (optional, recommended)

Without it the script still works (speechbrain + spectral clustering, ~93% speaker accuracy in
tests). With it, it uses **pyannote community-1** (~96%) and handles messy recordings better.

1. Create a free account at https://huggingface.co and a **read** token at
   https://huggingface.co/settings/tokens
2. Open https://huggingface.co/pyannote/speaker-diarization-community-1 and **accept the
   terms** (logged in). Without this the download is refused even with a token.
3. Save the token:

   ```bash
   mkdir -p ~/.cache/huggingface
   printf '%s' 'hf_xxx_your_token' > ~/.cache/huggingface/token
   chmod 600 ~/.cache/huggingface/token
   ```

   (or `export HF_TOKEN=hf_xxx` in your shell profile).

The token only downloads model weights. Your audio is processed locally and never uploaded.

## 4. Install the skills into your harness

A skill is just a folder with a `SKILL.md` (the [Agent Skills](https://agentskills.io) format).
Copy — or symlink, so `git pull` updates them — both folders from `skills/` into your harness's
skills directory:

| Harness | User-wide skills directory |
|---------|---------------------------|
| Claude Code | `~/.claude/skills/` (or `<project>/.claude/skills/` for one project) |
| OpenAI Codex CLI | `~/.codex/skills/` |
| Grok Build CLI | `~/.grok/skills/` |
| Harnesses that read the shared location | `~/.agents/skills/` (or `<project>/.agents/skills/`) |
| Anything else | Check your harness's docs for its skills folder |

Example (Claude Code, symlinked):

```bash
git clone https://github.com/giovannirco/interview-skills.git ~/src/interview-skills
mkdir -p ~/.claude/skills
ln -s ~/src/interview-skills/skills/interview-transcribe ~/.claude/skills/interview-transcribe
ln -s ~/src/interview-skills/skills/interview-process    ~/.claude/skills/interview-process
```

Same two `ln -s` lines with `~/.codex/skills` or `~/.grok/skills` for those tools. On Windows
use `mklink /D` or just copy the folders.

Restart the agent session. The skills show up as `/interview-transcribe` and
`/interview-process` (or are picked up automatically when you ask to transcribe an interview).

**No skills support in your tool?** Tell the agent: *"Read
`skills/interview-transcribe/SKILL.md` and follow it for this recording."* That's all a skill
is.

## 5. Where interviews are stored

By default `~/interviews/<company>-<role>/`. To use another place, set `INTERVIEWS_DIR`.
If you make it a git repo (recommended — private!), add this `.gitignore` first:

```gitignore
*.mov
*.mp4
*.mkv
*.m4a
*.mp3
*.wav
*.webm
*.aac
*.caf
```

## 6. Smoke test

Run the script by hand once, so model downloads happen now and not during your first real
interview. Any short recording with two people talking works — or record yourself for 30 s.

macOS/Linux:

```bash
~/.interview-transcribe/venv/bin/python skills/interview-transcribe/scripts/transcribe_interview.py \
  ~/Downloads/some-recording.m4a /tmp/it-test \
  --speakers "Me:candidate,Other" --num-speakers 2 --title "Smoke test"
cat /tmp/it-test/transcript-merged.md
```

You should see `audio track 1: …`, `ASR done…`, `pyannote done…` (or `segment-spectral
done…` without a token), then the path to `transcript-merged.md`.

First run downloads Whisper large-v3-turbo (~1.6 GB) and the diarization model.

## Recording tips

| Setup | Advice |
|-------|--------|
| **OBS** (any OS) | Record to `.mkv` (survives crashes; remux to mp4 later). Settings → Output → Recording → Audio Track: put Mic and Desktop Audio on **separate tracks** (Track 1 = mix, Track 2 = mic is a common setup). The script lists the tracks and mixes them by default; pass `--audio-track 1` if Track 1 already has everything |
| **macOS without OBS** | QuickTime screen recording does **not** capture the other side's audio by default. Use OBS (macOS 13+ captures app audio natively) or the meeting app's own recording |
| **Zoom local recording** | Turn on "Record a separate audio file for each participant" — perfect speaker separation for free |
| **Phone (Voice Memos etc.)** | Phone close to you, laptop speaker turned up. Expect your own voice to dominate; the skill has notes for this case |
| **Meet / Teams cloud recording** | Download the `.mp4`; works directly |

**Consent:** some companies forbid recording; some jurisdictions require everyone's consent.
Ask at the start of the call or don't record.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `pyannote failed (…401…/gated…)` then spectral fallback | Token missing or terms not accepted (step 3). The fallback output is still usable |
| `no audio stream in …` | The recording has no sound (common with QuickTime screen recording). Nothing to recover |
| Two people merged into one speaker | Re-run with `--reuse-asr` and `--auto-count`, or a different `--num-speakers`, or `--force-fallback`; compare |
| One person split into several speakers (phone recordings) | Lower `--num-speakers` to the number who actually spoke |
| Wrong language / gibberish | Pass `--language xx` (auto-detect only hears the first 30 s) |
| Names misspelled | `--initial-prompt "Company, Person, Tool"` and fix the rest by hand |
| Same word repeated dozens of times | Whisper hallucinating on silence; delete the loop in the merged file |
| Something broke after a fresh install | `requirements.txt` uses minimum versions; install the tested set from its header comment (e.g. `pip install torch==2.12.1 torchaudio==2.11.0 pyannote.audio==4.0.7`) |
| Very slow | You're on CPU. Fine for occasional use; `--asr-model small` for quick drafts |
