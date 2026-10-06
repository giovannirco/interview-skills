# Stack notes — interview-transcribe

Measured on an Apple Silicon Mac (M-series), 2026-08 → 2026-09.

## ASR

| Engine | Platform | Notes |
|--------|----------|-------|
| **mlx-whisper large-v3-turbo** | Apple Silicon | Default. ~20 s for a 24-min call, ~74 s for 69 min. Good English and Portuguese. |
| **faster-whisper large-v3-turbo** | Linux / Windows / Intel Mac (CUDA or CPU) | Used automatically when `mlx_whisper` is not installed. Same model family; slower on CPU. |
| whisper.cpp large-v3-turbo | Metal | Same quality tier; use if the Python env is broken. |
| WhisperX large | CUDA/CPU | Usable diarization glue; historically lower ASR quality than plain Whisper large. |

## Diarization

Reference file: a 24-minute, 3-person remote Google Meet call (candidate, recruiter,
hiring manager), mono. "Gold" = the hand-corrected merged transcript.

| Method | Needs | Frame accuracy vs gold | Use |
|--------|-------|------------------------|-----|
| pyannote community-1 **exclusive** | HF token + accepted terms, pyannote.audio 4.0.x | **95.9%** overall; weakest speaker 93.8%. 28.6 s on MPS, `num_speakers=3` | **Preferred** |
| segment ECAPA + spectral | speechbrain | **92.7%** overall; ~92% per speaker | **Fallback** when community-1 can't load |
| NVIDIA Nemotron 3 Diarization (offline) | mlx-audio 0.5.6 | 92.6%, recruiter only 79.3% (merged into candidate). On 6-speaker far-mic meetings it was the best (see `notsofar-6spk.md`) | 6-person room recordings only |
| segment ECAPA + agglomerative | speechbrain | ~75.6%; recruiter ~13% | Avoid on remote calls |
| windowed ECAPA agglomerative | speechbrain | ~77.6%; recruiter ~16% | Avoid (the original failure mode) |
| whisper tinydiarize | none | unusable | Never |

## How "frame accuracy" was measured

- Gold = QA-fixed merged transcript labels.
- Sample the timeline at 2 Hz; majority-vote map `SPEAKER_*` → gold names.
- Report overall + per-speaker accuracy. Per-speaker matters: an overall 77% hid a
  speaker who was right only 16% of the time.

## Failure modes

1. **No HF token / terms not accepted** → gated pyannote model can't load; script falls back to spectral automatically.
2. **Remote mono call** → far-end voices sound alike through the codec; windowed clustering merges them.
3. **Wrong `num_speakers`** → set the number of people who *spoke*; compare with `--auto-count`.
4. **Wrong name map** → content cues + human QA; never trust auto names alone.
5. **Strong accents** → higher word error; still usable for analysis with caveats.
6. Tuning Nemotron (activity threshold, cache size, presets) did not fix the recruiter merge;
   pyannote's clustering threshold does nothing while `num_speakers` is set.

## Hugging Face token (one-time, optional but recommended)

1. Create a **read** token at https://huggingface.co/settings/tokens
2. Accept the terms at https://huggingface.co/pyannote/speaker-diarization-community-1
3. `mkdir -p ~/.cache/huggingface && echo "<token>" > ~/.cache/huggingface/token && chmod 600 ~/.cache/huggingface/token`

The audio still never leaves the machine: the token only downloads model weights.
