"""Settings: .env loading and the model for each tier.

Model ids expire on free tiers. These were read from each provider's live model list on 2026-11-04;
re-check (scripts or the provider console) before an eval run. Only public docs text and demo questions are sent.
"""
from __future__ import annotations

import os
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS_VERIFIED = "2026-11-04"

# provider -> (OpenAI compatible base url, env var holding the key)
PROVIDERS = {
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "cerebras": ("https://api.cerebras.ai/v1", "CEREBRAS_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
}

# tier -> ordered (provider, model). The judge must be a different model family than the answer model.
TIERS = {
    "answer": [("groq", "openai/gpt-oss-120b"), ("cerebras", "gpt-oss-120b"), ("gemini", "gemini-3.5-flash-lite")],
    "fast": [("groq", "openai/gpt-oss-20b"), ("cerebras", "gpt-oss-120b")],
    "judge": [("gemini", "gemini-3.5-flash-lite"), ("gemini", "gemini-3.5-flash")],
}


def load_env(path: Path | None = None) -> None:
    """Load KEY=value lines, keeping only the first token so trailing comments cannot corrupt a key."""
    p = path or ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            tokens = shlex.split(v, comments=True)
            if tokens:
                os.environ.setdefault(k.strip(), tokens[0])
