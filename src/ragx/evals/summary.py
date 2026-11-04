"""Latest value of each key metric, read from eval/results/*.json, for the admin Evals tab.

Every row names its source file and the file's date, so a number on screen can always be traced to a run. Missing files are skipped.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

# (part, metric, file, path into the json, note)
REGISTRY = [
    ("retrieval", "hybrid hit@5, 30 baseline questions", "00-baseline.json", ["modes", "hybrid", "hit@5"], "page level, rag-demo set"),
    ("retrieval", "hybrid nDCG@10, dev split", "01-retrieval.json", ["modes", "hybrid", "dev", "ndcg@10"], "128 case golden set"),
    ("retrieval", "hybrid nDCG@10, held out split", "01-retrieval.json", ["modes", "hybrid", "held_out", "ndcg@10"], "not used to choose settings"),
    ("generation", "plain RAG faithfulness", "02-generation-v3-bracketfix.json", ["systems", "plain_rag", "overall", "faithfulness"], "judge: different model family; citations parsed after the bracket fix"),
    ("generation", "self-RAG faithfulness", "02-generation-v3-bracketfix.json", ["systems", "self_rag", "overall", "faithfulness"], ""),
    ("generation", "plain RAG answers with a citation", "02-generation-v3-bracketfix.json", ["systems", "plain_rag", "overall", "answers_with_a_citation"], ""),
    ("generation", "self-RAG answers with a citation", "02-generation-v3-bracketfix.json", ["systems", "self_rag", "overall", "answers_with_a_citation"], ""),
    ("generation", "judge agreement with labels", "02-judge-calibration.json", ["agreement"], "labels written by Claude, unreviewed"),
    ("pipeline", "plain RAG correct end to end", "03-system.json", ["systems", "plain_rag", "pipeline", "correct_overall"], "43 questions"),
    ("pipeline", "self-RAG correct end to end", "03-system.json", ["systems", "self_rag", "pipeline", "correct_overall"], ""),
    ("system", "semantic cache wrong hit rate at chosen threshold", "03-cache.json", ["chosen", "wrong_hit_rate"], "proxy: page overlap"),
    ("safety", "injection block rate", "04-safety.json", ["injection_block_rate"], "rule based, tuned on its own set"),
    ("safety", "false refusal on benign look alikes", "04-safety.json", ["benign_false_refusal_rate"], ""),
    ("memory", "follow up hit@5 with memory", "04-memory.json", ["memory_on", "hit@5"], "12 cases"),
    ("memory", "follow up hit@5 without memory", "04-memory.json", ["memory_off", "hit@5"], ""),
    ("voice", "word error rate (synthetic voices)", "05-voice-glossary.json", ["wer_mean"], "optimistic"),
    ("image", "key term recall (synthetic images)", "05-image.json", ["key_term_recall"], "optimistic"),
    ("image", "retrieval hit@5 from image (synthetic)", "05-image.json", ["hit@5"], "optimistic"),
]


def latest_results(results_dir: Path) -> list[dict]:
    out, cache = [], {}
    for part, metric, fname, path, note in REGISTRY:
        f = results_dir / fname
        if not f.exists():
            continue
        if fname not in cache:
            cache[fname] = json.loads(f.read_text(encoding="utf-8"))
        v = cache[fname]
        try:
            for k in path:
                v = v[k]
        except (KeyError, TypeError):
            continue  # the file exists but has no such field: skip rather than guess
        if isinstance(v, (int, float)):
            out.append({"part": part, "metric": metric, "value": v, "file": fname, "date": dt.datetime.fromtimestamp(f.stat().st_mtime).date().isoformat(), "note": note})
    return out
