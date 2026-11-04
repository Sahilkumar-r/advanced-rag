"""5.1 Build the SYNTHETIC voice set: 12 docs questions spoken by Windows text to speech (two voices), 6 of them again with noise.

python scripts/make_voice_set.py
These are clean machine voices, so word error rates measured on them are optimistic compared with a person speaking.
Writes eval/datasets/voice/*.wav and manifest.json. Needs Windows (pyttsx3 with the built in SAPI voices).
"""
import json
import wave
from pathlib import Path

import numpy as np
import pyttsx3

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "eval" / "datasets" / "voice"
SENTENCES = [  # numerals avoided on purpose: a spoken number has several correct spellings
    "How do I declare a path parameter in FastAPI?",
    "What is the difference between a before validator and an after validator in Pydantic?",
    "How do I allow requests from another origin using CORS middleware?",
    "How do I run a background task after returning a response?",
    "How do I validate a list of integers using a TypeAdapter?",
    "How do I upload a file with UploadFile and form fields?",
    "What does model underscore dump do in Pydantic version two?",
    "How do I use a discriminated union with a Literal tag field?",
    "How do I return a created status code from a POST endpoint?",
    "How do I read a cookie value in an endpoint?",
    "How do I serve static files with Uvicorn and FastAPI?",
    "How do I stop Pydantic from converting a string into an integer?",
]
RATES = [175, 150]


def speak(text: str, path: Path, voice: int, rate: int) -> None:
    e = pyttsx3.init()
    voices = e.getProperty("voices")
    e.setProperty("voice", voices[voice % len(voices)].id)
    e.setProperty("rate", rate)
    e.save_to_file(text, str(path))
    e.runAndWait()
    e.stop()


def add_noise(src: Path, dst: Path, snr_db: float, seed: int) -> None:
    with wave.open(str(src), "rb") as w:
        params, frames = w.getparams(), w.readframes(w.getnframes())
    x = np.frombuffer(frames, dtype=np.int16).astype(np.float64)
    noise = np.random.default_rng(seed).normal(0, 1, x.shape)
    noise *= np.sqrt((x ** 2).mean() / (10 ** (snr_db / 10))) / noise.std()
    y = np.clip(x + noise, -32768, 32767).astype(np.int16)
    with wave.open(str(dst), "wb") as w:
        w.setparams(params)
        w.writeframes(y.tobytes())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    items = []
    for i, text in enumerate(SENTENCES):
        voice, rate = i % 2, RATES[(i // 2) % 2]
        f = OUT / f"v{i:02d}.wav"
        speak(text, f, voice, rate)
        items.append({"id": f"v{i:02d}", "text": text, "file": f.name, "voice": voice, "rate": rate, "snr_db": None, "origin": "synthetic_tts"})
    for i in range(0, len(SENTENCES), 2):  # every second sentence again with noise
        src = OUT / f"v{i:02d}.wav"
        dst = OUT / f"v{i:02d}n.wav"
        add_noise(src, dst, 10.0, seed=i)
        items.append({**items[i], "id": f"v{i:02d}n", "file": dst.name, "snr_db": 10.0})
    (OUT / "manifest.json").write_text(json.dumps({"note": "SYNTHETIC: machine voices, optimistic. Replace or extend with real recordings when available.", "clips": items}, indent=1), encoding="utf-8")
    print(len(items), "clips,", sum(p.stat().st_size for p in OUT.glob("*.wav")) // 1024, "KB")


if __name__ == "__main__":
    main()
