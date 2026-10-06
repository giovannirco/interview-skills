#!/usr/bin/env python3
"""Interview transcription + diarization pipeline (Apple Silicon first).

Preferred stack:
  ASR: mlx-whisper large-v3-turbo on Apple Silicon; faster-whisper large-v3-turbo elsewhere
  Diarization:
    1) pyannote/speaker-diarization-community-1 if HF_TOKEN + terms accepted
    2) else speechbrain ECAPA on ASR segments + spectral clustering (num_speakers)

Outputs:
  - asr_raw.json
  - diarization_turns.json
  - segments_labeled.json
  - transcript-diarized.md
  - transcript-merged.md

Input can be any recording ffmpeg reads: a phone voice memo (.m4a), an OBS
video (.mkv/.mp4/.mov, one or several audio tracks), a Zoom/Meet/Teams
recording, or a ready 16 kHz mono WAV. Audio is extracted into OUT_DIR.

Usage:
  python transcribe_interview.py RECORDING OUT_DIR \\
    --speakers "Alex:candidate,Sam:recruiter,Jordan:hm" \\
    --num-speakers 3 \\
    [--title "Interview 1"]

Speaker hints are "Name" or "Name:role" (role = candidate | recruiter | hm).
A role tag lets the content cues pick the right cluster; untagged names are
assigned by talk time. Always verify the map by listening.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import subprocess

import numpy as np
import soundfile as sf

warnings.filterwarnings("ignore")


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def probe_audio_streams(src: Path) -> list[dict]:
    """Audio streams of a media file, via ffprobe."""
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index,codec_name,channels,sample_rate:stream_tags=title,handler_name",
         "-of", "json", str(src)],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        sys.exit(f"ffprobe failed on {src}: {res.stderr.strip()}")
    return json.loads(res.stdout or "{}").get("streams", [])


def prepare_audio(src: Path, out_dir: Path, track: str) -> Path:
    """Return a mono 16 kHz PCM WAV for src, extracting it into out_dir when needed.

    track: "1".."N" picks one audio track; "mix" mixes all tracks; "auto" uses the
    only track, or mixes when there are several (OBS multi-track recordings).
    """
    if src.suffix.lower() == ".wav":
        info = sf.info(str(src))
        if info.samplerate == 16000 and info.channels == 1 and track == "auto":
            return src
    streams = probe_audio_streams(src)
    if not streams:
        sys.exit(f"no audio stream in {src} (screen recordings without system/mic audio have none)")
    for i, st in enumerate(streams, 1):
        tags = st.get("tags") or {}
        log(f"audio track {i}: {st.get('codec_name')} {st.get('channels')}ch "
            f"{st.get('sample_rate')}Hz {tags.get('title') or tags.get('handler_name') or ''}".rstrip())
    wav = out_dir / "audio-mono-16k.wav"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vn"]
    if track == "auto":
        track = "1" if len(streams) == 1 else "mix"
    if track == "mix":
        n = len(streams)
        if n > 1:
            log(f"mixing {n} audio tracks (pick one with --audio-track N if track 1 is already the full mix)")
            inputs = "".join(f"[0:a:{k}]" for k in range(n))
            cmd += ["-filter_complex", f"{inputs}amix=inputs={n}:normalize=0[a]", "-map", "[a]"]
        else:
            cmd += ["-map", "0:a:0"]
    else:
        k = int(track) - 1
        if not 0 <= k < len(streams):
            sys.exit(f"--audio-track {track}: file has {len(streams)} audio track(s)")
        cmd += ["-map", f"0:a:{k}"]
    cmd += ["-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav)]
    log(f"extracting audio → {wav}")
    t0 = time.time()
    if subprocess.run(cmd).returncode != 0:
        sys.exit("ffmpeg extraction failed")
    log(f"extracted in {time.time()-t0:.1f}s")
    return wav


def get_hf_token() -> str | None:
    for key in ("HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        if os.environ.get(key):
            return os.environ[key].strip()
    for p in (
        Path.home() / ".cache/huggingface/token",
        Path.home() / ".huggingface/token",
    ):
        if p.exists():
            t = p.read_text().strip()
            if t:
                return t
    return None


def pick_asr_backend(requested: str) -> str:
    if requested != "auto":
        return requested
    try:
        import mlx_whisper  # noqa: F401  (Apple Silicon only)
        return "mlx"
    except ImportError:
        return "faster-whisper"


def run_asr(
    audio: Path,
    language: str | None = None,
    initial_prompt: str | None = None,
    backend: str = "auto",
    model: str = "",
) -> tuple[dict, str]:
    backend = pick_asr_backend(backend)
    extra = {}
    if language:
        extra["language"] = language  # e.g. "pt"; auto-detect reads only the first 30s
    if initial_prompt:
        extra["initial_prompt"] = initial_prompt  # names and product terms, spelled as wanted
    t0 = time.time()

    if backend == "mlx":
        import mlx_whisper

        repo = model or "mlx-community/whisper-large-v3-turbo"
        log(f"ASR mlx-whisper {repo}: {audio} language={language or 'auto'}")
        result = mlx_whisper.transcribe(
            str(audio),
            path_or_hf_repo=repo,
            word_timestamps=True,
            verbose=False,
            **extra,
        )
        label = f"mlx-whisper {repo.split('/')[-1]}"
    else:
        from faster_whisper import WhisperModel

        name = model or "large-v3-turbo"
        log(f"ASR faster-whisper {name}: {audio} language={language or 'auto'}")
        try:
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
        fw = WhisperModel(name, device=device, compute_type="float16" if device == "cuda" else "int8")
        # Pass decoded samples: faster-whisper's own file decoding breaks with newer PyAV releases.
        wav, sr = sf.read(str(audio), dtype="float32")
        if wav.ndim > 1:
            wav = wav.mean(axis=1)
        if sr != 16000:
            sys.exit(f"expected 16 kHz audio, got {sr} Hz; re-extract with ffmpeg -ar 16000")
        seg_iter, info = fw.transcribe(wav, word_timestamps=True, **extra)
        segments = [
            {"id": i, "start": float(sg.start), "end": float(sg.end), "text": sg.text}
            for i, sg in enumerate(seg_iter)
        ]
        result = {
            "text": "".join(sg["text"] for sg in segments),
            "segments": segments,
            "language": info.language,
        }
        label = f"faster-whisper {name}"
    log(f"ASR done in {time.time()-t0:.1f}s segments={len(result.get('segments') or [])}")
    return result, label


def diar_pyannote(audio: Path, n_speakers: int | None, token: str):
    from pyannote.audio import Pipeline
    import torch

    log("Diarization: pyannote community-1 (waveform in-memory + exclusive)")
    t0 = time.time()
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-community-1", token=token
    )
    if torch.cuda.is_available():
        pipeline.to(torch.device("cuda"))
    elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        try:
            pipeline.to(torch.device("mps"))
        except Exception:
            pass
    wav, sr = sf.read(str(audio))
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    waveform = torch.from_numpy(np.ascontiguousarray(wav)).float().unsqueeze(0)
    diarization = pipeline(
        {"waveform": waveform, "sample_rate": int(sr)},
        num_speakers=n_speakers,
    )
    exclusive = getattr(diarization, "exclusive_speaker_diarization", None)
    tracks = exclusive if exclusive is not None else getattr(
        diarization, "speaker_diarization", diarization
    )
    turns = []
    for turn, _, speaker in tracks.itertracks(yield_label=True):
        turns.append({"start": float(turn.start), "end": float(turn.end), "speaker": speaker})
    method = "pyannote-community-1-exclusive" if exclusive is not None else "pyannote-community-1"
    log(f"pyannote done in {time.time()-t0:.1f}s turns={len(turns)} method={method}")
    return turns, method


def diar_segment_spectral(audio: Path, asr_segments: list, n_speakers: int, cache_dir: Path):
    import torch
    from speechbrain.inference.speaker import EncoderClassifier
    from sklearn.cluster import SpectralClustering
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.preprocessing import normalize

    log("Diarization: segment-ECAPA + spectral clustering (fallback)")
    t0 = time.time()
    classifier = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir=str(cache_dir / "spkrec-ecapa-voxceleb"),
        run_opts={"device": "cpu"},
    )
    wav, sr = sf.read(str(audio))
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    embeds, meta = [], []
    for seg in asr_segments:
        s, e = float(seg["start"]), float(seg["end"])
        if e - s < 0.35:
            continue
        a, b = int(s * sr), int(e * sr)
        chunk = wav[a:b]
        if len(chunk) < int(0.35 * sr):
            continue
        if len(chunk) < int(0.5 * sr):
            chunk = np.pad(chunk, (0, int(0.5 * sr) - len(chunk)))
        maxn = int(8 * sr)
        if len(chunk) > maxn:
            mid = len(chunk) // 2
            chunk = chunk[mid - maxn // 2 : mid + maxn // 2]
        tensor = torch.tensor(chunk, dtype=torch.float32).unsqueeze(0)
        with torch.no_grad():
            emb = classifier.encode_batch(tensor).squeeze().cpu().numpy()
        embeds.append(emb)
        meta.append((s, e))
    if len(embeds) < n_speakers:
        raise RuntimeError(f"too few speech segments for clustering: {len(embeds)}")
    X = normalize(np.stack(embeds))
    sim = np.clip(cosine_similarity(X), 0, 1)
    labels = SpectralClustering(
        n_clusters=n_speakers, affinity="precomputed", assign_labels="kmeans", random_state=0
    ).fit_predict(sim)
    turns = [
        {"start": s, "end": e, "speaker": f"SPEAKER_{int(lab):02d}"}
        for (s, e), lab in zip(meta, labels)
    ]
    log(f"segment-spectral done in {time.time()-t0:.1f}s turns={len(turns)}")
    return turns, "segment-ecapa-spectral"


def speaker_at(turns, t: float) -> str:
    for tr in turns:
        if tr["start"] <= t <= tr["end"]:
            return tr["speaker"]
    best, best_d = "UNKNOWN", 1e9
    for tr in turns:
        mid = 0.5 * (tr["start"] + tr["end"])
        d = abs(mid - t)
        if d < best_d:
            best_d, best = d, tr["speaker"]
    return best


def assign_segments(asr_segments, turns):
    out = []
    for seg in asr_segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        mid = 0.5 * (float(seg["start"]) + float(seg["end"]))
        out.append(
            {
                "start": float(seg["start"]),
                "end": float(seg["end"]),
                "speaker": speaker_at(turns, mid),
                "text": text,
            }
        )
    # merge adjacent same speaker
    merged = []
    for s in out:
        if merged and merged[-1]["speaker"] == s["speaker"] and s["start"] - merged[-1]["end"] < 1.2:
            merged[-1]["end"] = s["end"]
            merged[-1]["text"] = (merged[-1]["text"] + " " + s["text"]).strip()
        else:
            merged.append(dict(s))
    return merged


# Lightweight content cues for common interview roles (override cluster ids)
CUE_PATTERNS = {
    "recruiter_ta": re.compile(
        r"\b(head of talent|talent partner|recruiter|next steps in the process|"
        r"technical interview|not a technical assessment|let me get back to you)\b",
        re.I,
    ),
    "hiring_manager": re.compile(
        r"\b(VP of Engineering|I will have to drop|that gives me a nice picture|"
        r"tell me,|my team|on my team|sprint planning|the roadmap)\b",
        re.I,
    ),
    "candidate": re.compile(
        r"\b(I built|I shipped|my experience|I was at|in my current role|"
        r"I'm usually flexible|I did some research)\b",
        re.I,
    ),
}


def auto_name_speakers(labeled: list, name_hints: list[str] | None) -> dict[str, str]:
    """Map SPEAKER_* → human names using talk-time + optional ordered hints + cues."""
    talk = Counter()
    cue_hits = defaultdict(Counter)
    for s in labeled:
        sp = s["speaker"]
        talk[sp] += max(0.0, s["end"] - s["start"])
        t = s["text"]
        for cue, pat in CUE_PATTERNS.items():
            if pat.search(t):
                cue_hits[sp][cue] += 1

    clusters = sorted(talk.keys(), key=lambda k: -talk[k])
    mapping: dict[str, str] = {}

    # If user gave ordered names matching num speakers, map by talk-time rank only as weak prior
    # Prefer cue-based assignment when hints look role-like.
    # Hints are "Name" or "Name:role"; a role tag lets cue hits pick the cluster.
    role_alias = {
        "candidate": "candidate", "me": "candidate",
        "recruiter": "recruiter_ta", "ta": "recruiter_ta", "talent": "recruiter_ta",
        "hm": "hiring_manager", "manager": "hiring_manager", "hiring_manager": "hiring_manager",
    }
    hints = []
    role_to_hint = {}
    for raw in name_hints or []:
        name, _, role = raw.partition(":")
        name = name.strip()
        hints.append(name)
        role = role_alias.get(role.strip().lower())
        if role:
            role_to_hint[role] = name

    used_names = set()
    used_clusters = set()
    if role_to_hint:
        for cluster, hits in cue_hits.items():
            if not hits:
                continue
            top_cue = hits.most_common(1)[0][0]
            if top_cue in role_to_hint and cluster not in used_clusters:
                name = role_to_hint[top_cue]
                if name not in used_names:
                    mapping[cluster] = name
                    used_names.add(name)
                    used_clusters.add(cluster)

    # Fill remaining by talk time order vs remaining hints
    remaining_hints = [h for h in hints if h not in used_names]
    remaining_clusters = [c for c in clusters if c not in used_clusters]
    for c, h in zip(remaining_clusters, remaining_hints):
        mapping[c] = h
        used_names.add(h)
        used_clusters.add(c)
    # leftover clusters keep SPEAKER id
    for c in clusters:
        mapping.setdefault(c, c)
    return mapping


def fmt_ts(sec: float) -> str:
    m = int(sec // 60)
    s = sec - 60 * m
    return f"{m}:{s:05.2f}"


def write_markdown(
    out_dir: Path,
    labeled: list,
    title: str,
    method: str,
    speaker_map: dict,
    audio_name: str,
    asr_label: str,
):
    # apply map
    for s in labeled:
        s["speaker"] = speaker_map.get(s["speaker"], s["speaker"])

    talk = Counter()
    for s in labeled:
        talk[s["speaker"]] += max(0.0, s["end"] - s["start"])

    diar_lines = [
        f"# {title} — Diarized transcript",
        "",
        f"**Source audio:** `{audio_name}`",
        f"**Pipeline:** {asr_label} + {method}",
        f"**Speakers:** {', '.join(f'{k} (~{v:.0f}s)' for k,v in talk.most_common())}",
        "",
        "## Speaker map",
        "",
        "| Cluster → Name | Talk time |",
        "|----------------|----------:|",
    ]
    # reverse map note
    for raw, name in speaker_map.items():
        diar_lines.append(f"| {raw} → **{name}** | {talk.get(name, 0):.0f}s |")
    diar_lines += [
        "",
        "## QA checklist",
        "",
        "- [ ] Spot-check open / mid / close against audio",
        "- [ ] Fix any SPEAKER_* left unmapped",
        "- [ ] Fix systematic ASR name errors (company, tools)",
        "- [ ] Prefer merged file as analysis SoT",
        "",
        "## Transcript",
        "",
    ]
    for s in labeled:
        diar_lines.append(f"[{s['speaker']}] ({s['start']:.1f}s - {s['end']:.1f}s)")
        diar_lines.append(s["text"])
        diar_lines.append("")
    (out_dir / "transcript-diarized.md").write_text("\n".join(diar_lines) + "\n", encoding="utf-8")

    merged = [
        f"# {title} — Merged transcript (analysis SoT)",
        "",
        f"**Pipeline:** {asr_label} + {method}",
        f"**Companion:** transcript-diarized.md",
        "",
        "## Transcript",
        "",
    ]
    for s in labeled:
        merged.append(f"**{s['speaker']}** [{fmt_ts(s['start'])}–{fmt_ts(s['end'])}]")
        merged.append("")
        merged.append(s["text"])
        merged.append("")
    (out_dir / "transcript-merged.md").write_text("\n".join(merged) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("recording", type=Path, help="Video or audio file (mkv/mp4/mov/m4a/mp3/wav…)")
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--speakers", default="", help='Comma names, optionally role-tagged: "Alex:candidate,Sam:recruiter,Jordan:hm"')
    ap.add_argument("--num-speakers", type=int, default=0, help="Speakers who actually talked (default: number of --speakers)")
    ap.add_argument("--auto-count", action="store_true", help="Let pyannote pick the speaker count (compare against a forced count)")
    ap.add_argument("--title", default="Interview")
    ap.add_argument("--audio-track", default="auto", help='"auto" (default), "mix", or a track number 1..N')
    ap.add_argument("--force-fallback", action="store_true", help="Skip pyannote even if token")
    ap.add_argument("--language", default="", help="Whisper language code, e.g. pt or en (default: auto-detect)")
    ap.add_argument("--initial-prompt", default="", help="Names/terms to prime spelling, e.g. 'Acme, Priya, Kubernetes'")
    ap.add_argument("--asr-backend", choices=["auto", "mlx", "faster-whisper"], default="auto")
    ap.add_argument("--asr-model", default="", help="Override the Whisper model (e.g. 'small' for a quick test)")
    ap.add_argument("--reuse-asr", action="store_true", help="Reuse OUT_DIR/asr_raw.json; only re-run diarization")
    args = ap.parse_args()

    src = args.recording.expanduser().resolve()
    out = args.out_dir.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        sys.exit(f"recording not found: {src}")
    audio = prepare_audio(src, out, args.audio_track)

    hints = [s.strip() for s in args.speakers.split(",") if s.strip()]
    n_speakers = args.num_speakers or (len(hints) if hints else 2)
    if n_speakers < 2:
        n_speakers = 2

    asr_path = out / "asr_raw.json"
    if args.reuse_asr and asr_path.exists():
        asr = json.loads(asr_path.read_text(encoding="utf-8"))
        asr_label = asr.get("_asr_label", "whisper (reused)")
        log(f"Reusing {asr_path}")
    else:
        asr, asr_label = run_asr(
            audio, args.language or None, args.initial_prompt or None,
            args.asr_backend, args.asr_model,
        )
        asr["_asr_label"] = asr_label
        asr_path.write_text(json.dumps(asr), encoding="utf-8")
    segs = asr.get("segments") or []

    token = None if args.force_fallback else get_hf_token()
    method = ""
    turns = None
    if token:
        try:
            turns, method = diar_pyannote(audio, None if args.auto_count else n_speakers, token)
        except Exception as e:
            log(f"pyannote failed ({e}); falling back")
            turns = None
    if turns is None:
        turns, method = diar_segment_spectral(audio, segs, n_speakers, out)

    (out / "diarization_turns.json").write_text(
        json.dumps({"method": method, "turns": turns}, indent=2), encoding="utf-8"
    )
    labeled = assign_segments(segs, turns)
    speaker_map = auto_name_speakers(labeled, hints or None)
    # apply for JSON export
    labeled_named = []
    for s in labeled:
        labeled_named.append({**s, "speaker_raw": s["speaker"], "speaker": speaker_map.get(s["speaker"], s["speaker"])})
    (out / "segments_labeled.json").write_text(json.dumps(labeled_named, indent=2), encoding="utf-8")
    (out / "speaker_map.json").write_text(json.dumps(speaker_map, indent=2), encoding="utf-8")

    write_markdown(out, [dict(s) for s in labeled], args.title, method, speaker_map, src.name, asr_label)
    stats = {
        "asr": asr_label,
        "method": method,
        "n_segments": len(segs),
        "n_turns_merged": len(labeled_named),
        "speaker_map": speaker_map,
    }
    talk = Counter()
    for s in labeled_named:
        talk[s["speaker"]] += max(0.0, s["end"] - s["start"])
    stats["talk_seconds"] = {k: round(v, 1) for k, v in talk.items()}
    (out / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    log(json.dumps(stats, indent=2))
    print(str(out / "transcript-merged.md"))


if __name__ == "__main__":
    main()
