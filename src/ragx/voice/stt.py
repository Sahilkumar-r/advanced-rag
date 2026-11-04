"""5.1 Speech to text with Groq Whisper, plus the word error rate used to check it.

Audio is processed in memory and dropped: nothing is written to disk. Only short clips of docs questions are sent
(free tier prompts may be used for training). The caller shows the transcript for the user to confirm before it is used as a question.
"""
from __future__ import annotations

import os
import re

import httpx

from ragx.config import PROVIDERS, load_env
from ragx.generate.providers import ProviderError

MODELS = ["whisper-large-v3", "whisper-large-v3-turbo"]  # both listed by Groq on 2026-11-04; the second is the fallback
MAX_BYTES = 4 * 1024 * 1024


def sniff_audio(b: bytes) -> str | None:
    """File type from the first bytes, so a renamed file cannot sneak through on its extension. None if not audio we accept."""
    if b[:4] == b"RIFF" and b[8:12] == b"WAVE":
        return "wav"
    if b[:3] == b"ID3" or (len(b) > 1 and b[0] == 0xFF and b[1] & 0xE0 == 0xE0):
        return "mp3"
    if b[:4] == b"OggS":
        return "ogg"
    if b[:4] == b"fLaC":
        return "flac"
    if b[4:8] == b"ftyp":
        return "m4a"
    if b[:4] == b"\x1aE\xdf\xa3":
        return "webm"
    return None


GLOSSARY = "FastAPI, Pydantic, Uvicorn, Starlette, TypeAdapter, UploadFile, BaseModel, model_dump, model_validate, CORS, HTTPException, Depends, Query, Path"


def transcribe(audio: bytes, kind: str, post=httpx.post, prompt: str = "") -> str:
    """prompt is Whisper's vocabulary hint (for example GLOSSARY): it biases spelling of names, it is not an instruction."""
    load_env()
    key = os.environ.get(PROVIDERS["groq"][1], "")
    if not key:
        raise ProviderError("groq", None, "no API key configured")
    base = PROVIDERS["groq"][0]
    errors = []
    for model in MODELS:
        try:
            r = post(f"{base}/audio/transcriptions", headers={"Authorization": f"Bearer {key}"}, files={"file": (f"clip.{kind}", audio)},
                     data={"model": model, "language": "en", "temperature": "0", "response_format": "json", **({"prompt": prompt} if prompt else {})}, timeout=60)
        except httpx.HTTPError as e:
            errors.append(f"{model}: {type(e).__name__}")
            continue
        if r.status_code == 200:
            return (r.json().get("text") or "").strip()
        errors.append(f"{model}: {r.status_code}")
    raise ProviderError("groq", None, "; ".join(errors))


_NUM = {str(i): w for i, w in enumerate("zero one two three four five six seven eight nine ten".split())}  # "2" and "two" are the same word


def _words(s: str) -> list[str]:
    s = re.sub(r"\bfast[\s-]?api\b", "fastapi", s.lower())  # one word however it is spelled; not an error to hear it either way
    return [_NUM.get(w, w) for w in re.findall(r"[a-z0-9']+", s.replace("-", " "))]


def wer(reference: str, hypothesis: str) -> float:
    """Word error rate: (substitutions + deletions + insertions) / reference words, after lowercasing and dropping punctuation."""
    r, h = _words(reference), _words(hypothesis)
    prev = list(range(len(h) + 1))
    for i, rw in enumerate(r, 1):
        cur = [i]
        for j, hw in enumerate(h, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rw != hw)))
        prev = cur
    return prev[-1] / len(r) if r else 0.0
