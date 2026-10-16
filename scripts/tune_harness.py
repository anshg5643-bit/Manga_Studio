"""Grid-search the non-learned knobs (ordering alpha, rtl, speaker mode, keep threshold) on the dev set with the
LOCAL PROXY scorer. Uses the OCR cache so after the first pass it is fast.  Pick on a held-out split of
sequences, not on the whole dev set, if you want an honest number (--val-frac)."""
import argparse, os, sys, json, itertools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mangapipe import analyze_sequence, PipelineConfig
from mangapipe.data import load_sequences, load_jsonl, split_by_sequence
from mangapipe.scoring import score_all

ap = argparse.ArgumentParser()
ap.add_argument("--seq-root", required=True); ap.add_argument("--sequences-json")
ap.add_argument("--labels", required=True); ap.add_argument("--val-frac", type=float, default=0.25)
ap.add_argument("--out-config", default="config.json"); ap.add_argument("--log", default="outputs/tune_log.json")
a = ap.parse_args()
refs = {r["sequence_id"]: r["pages"] for r in load_jsonl(a.labels)}
seqs = load_sequences(a.seq_root, a.sequences_json)
train_ids, val_ids = split_by_sequence(list(refs), a.val_frac)
grid = dict(alpha=[0.5, 1.0, 2.0], speaker_mode=["alternate", "appearance", "single"],
            keep_threshold=[0.4, 0.5, 0.6], use_panels=[True, False])
log, best = [], None
for vals in itertools.product(*grid.values()):
    cfg = PipelineConfig(**dict(zip(grid, vals)))
    preds = {sid: analyze_sequence(seqs[sid], cfg)["pages"] for sid in train_ids}
    m, _ = score_all(preds, {s: refs[s] for s in train_ids})
    log.append(dict(cfg=dict(zip(grid, vals)), **m)); print(log[-1], flush=True)
    if best is None or m["text_order_score"] + m["balanced_joint_f1"] > best[0]:
        best = (m["text_order_score"] + m["balanced_joint_f1"], cfg)
cfg = best[1]
preds = {sid: analyze_sequence(seqs[sid], cfg)["pages"] for sid in val_ids}
vm, _ = score_all(preds, {s: refs[s] for s in val_ids})
print("BEST", cfg, "held-out:", vm)
os.makedirs(os.path.dirname(a.log), exist_ok=True)
json.dump(dict(grid=log, best=cfg.__dict__, heldout=vm), open(a.log, "w"), indent=2)
json.dump(cfg.__dict__, open(a.out_config, "w"), indent=2)
