"""Transcribe a video locally (free, offline) with word timestamps.

Usage: python scripts/transcribe.py <video> <draft_dir> [--model small] [--language en]

Writes <draft_dir>/transcript.json (segments + words) and transcript.txt (readable, timestamped).
The first run downloads the Whisper model (~460 MB for "small"); later runs are offline.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from common import env, find_tool, probe


def transcribe(video: str, out_dir: Path, model_name: str, language: str | None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    info = probe(video)
    result = {"source": str(video), "duration": info["duration"], "language": None, "segments": []}
    if not info["has_audio"]:
        print("Video has no audio track - writing an empty transcript.")
    else:
        import numpy as np
        from faster_whisper import WhisperModel

        # Decode with our ffmpeg (16 kHz mono float) instead of faster-whisper's PyAV decoder.
        pcm = subprocess.run([find_tool("ffmpeg"), "-v", "error", "-i", str(video), "-vn", "-ac", "1",
                              "-ar", "16000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
        audio = np.frombuffer(pcm, dtype=np.float32)
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        segments, meta = model.transcribe(audio, word_timestamps=True, vad_filter=True, language=language)
        result["language"] = meta.language
        for s in segments:
            result["segments"].append({
                "start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
                "words": [{"start": round(w.start, 2), "end": round(w.end, 2), "word": w.word.strip()}
                          for w in (s.words or []) if w.word.strip()],
            })
    (out_dir / "transcript.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [f"[{s['start']:7.2f} - {s['end']:7.2f}] {s['text']}" for s in result["segments"]]
    (out_dir / "transcript.txt").write_text("\n".join(lines) or "(no speech)", encoding="utf-8")
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("draft_dir")
    ap.add_argument("--model", default=env("WHISPER_MODEL", "small"))
    ap.add_argument("--language", default=env("WHISPER_LANGUAGE"))
    a = ap.parse_args()
    r = transcribe(a.video, Path(a.draft_dir), a.model, a.language)
    words = sum(len(s["words"]) for s in r["segments"])
    print(f"Language: {r['language']}, {len(r['segments'])} segments, {words} words")
    print(f"Wrote {Path(a.draft_dir) / 'transcript.txt'}")
