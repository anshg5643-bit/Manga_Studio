"""Generate the test JSONL from images only (no manual edits).
python scripts/run_infer.py --seq-root <dir with seq_*/01.png..> --out outputs/test_predictions.jsonl
Optional: --ids sample_submission.jsonl to keep the official order of sequence ids."""
import argparse, os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mangapipe import analyze_sequence, PipelineConfig
from mangapipe.data import load_sequences, load_jsonl, save_jsonl

ap = argparse.ArgumentParser()
ap.add_argument("--seq-root", required=True)
ap.add_argument("--sequences-json")
ap.add_argument("--ids")
ap.add_argument("--out", required=True)
ap.add_argument("--config", default="config.json")
ap.add_argument("--backend")
a = ap.parse_args()

cfg = PipelineConfig.from_file(a.config)
if a.backend:
    cfg.backend = a.backend
seqs = load_sequences(a.seq_root, a.sequences_json)
ids = [r["sequence_id"] for r in load_jsonl(a.ids)] if a.ids else list(seqs)
rows, t0 = [], time.time()
for sid in ids:
    res = analyze_sequence(seqs[sid], cfg)
    pages = res["pages"] + [[]] * (3 - len(res["pages"]))
    rows.append(dict(sequence_id=sid, pages=pages))
    print(f"{sid}: {[len(p) for p in pages]} lines  ({time.time() - t0:.0f}s)", flush=True)
save_jsonl(rows, a.out)
print("wrote", a.out, "| config:", cfg)
