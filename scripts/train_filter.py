"""Train the learned 'keep this text block?' filter on the dev labels (sequence-level GroupKFold CV).
python scripts/train_filter.py --seq-root dev_dir --labels labels.jsonl"""
import argparse, os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mangapipe import data
from mangapipe.train import train_filter

ap = argparse.ArgumentParser()
ap.add_argument("--seq-root", required=True); ap.add_argument("--sequences-json")
ap.add_argument("--labels", required=True); ap.add_argument("--log", default="outputs/train_filter_log.json")
a = ap.parse_args()
seqs = data.load_sequences(a.seq_root, a.sequences_json)
refs = {r["sequence_id"]: r["pages"] for r in data.load_jsonl(a.labels)}
rep = train_filter(seqs, refs, progress=lambda i, n: print(f"collected {i}/{n}", flush=True))
print(json.dumps(rep, indent=2))
os.makedirs(os.path.dirname(a.log), exist_ok=True)
json.dump(rep, open(a.log, "w"), indent=2)
print("saved models/keep_filter.pkl")
