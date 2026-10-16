"""Score predictions vs development labels with the LOCAL PROXY scorer (also run the official score.py!).
python scripts/evaluate.py --seq-root dev_dir --labels labels.jsonl [--predictions preds.jsonl]
Without --predictions it runs the pipeline on every sequence in labels.jsonl."""
import argparse, os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mangapipe import analyze_sequence, PipelineConfig
from mangapipe.data import load_sequences, load_jsonl
from mangapipe.scoring import score_all

ap = argparse.ArgumentParser()
ap.add_argument("--seq-root"); ap.add_argument("--sequences-json")
ap.add_argument("--labels", required=True); ap.add_argument("--predictions")
ap.add_argument("--config", default="config.json"); ap.add_argument("--out", default="outputs/dev_scores.json")
a = ap.parse_args()
refs = {r["sequence_id"]: r["pages"] for r in load_jsonl(a.labels)}
if a.predictions:
    preds = {r["sequence_id"]: r["pages"] for r in load_jsonl(a.predictions)}
else:
    cfg = PipelineConfig.from_file(a.config)
    seqs = load_sequences(a.seq_root, a.sequences_json)
    preds = {sid: analyze_sequence(seqs[sid], cfg)["pages"] for sid in refs}
mean, rows = score_all(preds, refs)
print(json.dumps(mean, indent=2))
os.makedirs(os.path.dirname(a.out), exist_ok=True)
json.dump(dict(mean=mean, per_sequence=rows), open(a.out, "w"), indent=2)
