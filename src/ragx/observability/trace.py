"""3.3 JSONL tracing. One line per query. The question is stored as a hash, not text, so traces can be shared."""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path

from ragx.config import ROOT


class Tracer:
    def __init__(self, path: Path | None = None):
        self.path = path or ROOT / "traces" / "traces.jsonl"

    def record(self, question: str, **fields) -> dict:
        row = {"trace_id": uuid.uuid4().hex[:12], "ts": round(time.time(), 3), "question_hash": hashlib.sha256(question.encode()).hexdigest()[:16], **fields}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")
        return row
