"""5.1 Word error rate of the speech to text path on the synthetic voice set.

python scripts/run_voice_eval.py
Also checks that the transcript, used as a question, reaches the same top retrieved page as the typed sentence does.
Writes eval/results/05-voice.json. Numbers are for SYNTHETIC machine voices and are optimistic.
"""
import argparse
import json
import statistics as st
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragx.ingest.parent_child import chunk_pages  # noqa: E402
from ragx.retrieve.hybrid import Retriever  # noqa: E402
from ragx.voice import stt  # noqa: E402

DIR = ROOT / "eval" / "datasets" / "voice"
RAW, CACHE = ROOT / "data" / "raw", ROOT / "data" / "index" / "cache"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--glossary", action="store_true", help="send the docs vocabulary as Whisper's prompt")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    clips = json.loads((DIR / "manifest.json").read_text(encoding="utf-8"))["clips"]
    pages = {f"{p.parent.name}/{p.name}": p.read_text(encoding="utf-8") for d in ("fastapi", "pydantic") for p in sorted((RAW / d).glob("*.md"))}
    _, children = chunk_pages(pages, 256, 0.0)
    retr = Retriever(children, cache_dir=CACHE)
    rows = []
    for c in clips:
        data = (DIR / c["file"]).read_bytes()
        t = time.perf_counter()
        try:
            hyp = stt.transcribe(data, stt.sniff_audio(data), prompt=stt.GLOSSARY if args.glossary else "")
        except Exception as e:  # recorded, never hidden
            rows.append({**c, "error": str(e)[:120]})
            print(c["id"], "ERROR", str(e)[:80], flush=True)
            continue
        ms = (time.perf_counter() - t) * 1000
        top_typed = [h.doc for h in retr.search(c["text"], "hybrid", k=3)]
        top_voice = [h.doc for h in retr.search(hyp, "hybrid", k=3)]
        rows.append({**c, "transcript": hyp, "wer": round(stt.wer(c["text"], hyp), 4), "ms": round(ms), "same_top1_page": top_typed[0] == top_voice[0], "same_top3_set": set(top_typed) == set(top_voice)})
        print(c["id"], rows[-1]["wer"], hyp[:70], flush=True)
    ok = [r for r in rows if "wer" in r]
    grp = lambda f: [r["wer"] for r in ok if f(r)]
    out = {"synthetic": True, "glossary_prompt": args.glossary, "n": len(rows), "errors": len(rows) - len(ok),
           "wer_mean": round(st.mean(r["wer"] for r in ok), 4), "wer_clean_mean": round(st.mean(grp(lambda r: r["snr_db"] is None)), 4),
           "wer_noisy_mean": round(st.mean(grp(lambda r: r["snr_db"] is not None)), 4), "clips_with_zero_errors": sum(r["wer"] == 0 for r in ok),
           "same_top1_page_rate": round(st.mean(float(r["same_top1_page"]) for r in ok), 4), "p50_ms": round(st.median(r["ms"] for r in ok)),
           "models": stt.MODELS, "rows": rows}
    (ROOT / "eval" / "results" / f"05-voice{'-' + args.tag if args.tag else ''}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print({k: v for k, v in out.items() if k != "rows"})


if __name__ == "__main__":
    main()
