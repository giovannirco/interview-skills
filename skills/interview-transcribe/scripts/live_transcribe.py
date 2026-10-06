#!/usr/bin/env python3
"""
Near-live transcription: captures rolling audio chunks from the microphone
and transcribes each chunk as it completes, using mlx-whisper.

Not true streaming (no mid-word partial results) - trades a few seconds of
latency per chunk for reliability, using only pieces already proven to work.
"""
import sys
import time
import queue
import numpy as np
import sounddevice as sd
import mlx_whisper

SAMPLE_RATE = 16000
CHUNK_SECONDS = 8

def record_chunks(q, stop_event):
    def callback(indata, frames, time_info, status):
        q.put(indata.copy())

    with sd.InputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=callback
    ):
        while not stop_event.is_set():
            time.sleep(0.1)

def main():
    import threading

    q = queue.Queue()
    stop_event = threading.Event()
    recorder = threading.Thread(target=record_chunks, args=(q, stop_event), daemon=True)
    recorder.start()

    print(f"Listening (Ctrl+C to stop). Transcribing every ~{CHUNK_SECONDS}s...\n", file=sys.stderr)

    buffer = []
    buffered_seconds = 0.0
    try:
        while True:
            block = q.get()
            buffer.append(block)
            buffered_seconds += len(block) / SAMPLE_RATE

            if buffered_seconds >= CHUNK_SECONDS:
                audio = np.concatenate(buffer, axis=0).flatten()
                buffer = []
                buffered_seconds = 0.0

                if np.abs(audio).max() < 0.01:
                    continue  # skip near-silent chunks

                result = mlx_whisper.transcribe(
                    audio,
                    path_or_hf_repo="mlx-community/whisper-large-v3-turbo",
                )
                text = result["text"].strip()
                if text:
                    ts = time.strftime("%H:%M:%S")
                    print(f"[{ts}] {text}")
    except KeyboardInterrupt:
        stop_event.set()
        print("\nStopped.", file=sys.stderr)

if __name__ == "__main__":
    main()
