"""Dataset helpers. Works with the zip layout  <root>/<sequence_id>/01.png 02.png 03.png
or with a sequences.json (dict id->[3 paths]  or  list of {sequence_id|id, images|pages|paths:[...]})."""
import json, os, glob
from typing import Dict, List


def load_sequences(root: str, sequences_json: str = None) -> Dict[str, List[str]]:
    seqs: Dict[str, List[str]] = {}
    if sequences_json and os.path.exists(sequences_json):
        raw = json.load(open(sequences_json))
        base = os.path.dirname(os.path.abspath(sequences_json))
        items = raw.items() if isinstance(raw, dict) else [
            (r.get("sequence_id") or r.get("id"), r.get("images") or r.get("pages") or r.get("paths")) for r in raw]
        for sid, paths in items:
            fixed = []
            for p in paths:
                cand = [p, os.path.join(base, p), os.path.join(root, p), os.path.join(root, os.path.basename(p))]
                fixed.append(next((c for c in cand if os.path.exists(c)), p))
            seqs[sid] = fixed
        return seqs
    for d in sorted(glob.glob(os.path.join(root, "*"))):
        if os.path.isdir(d):
            imgs = sorted(glob.glob(os.path.join(d, "*.png")) + glob.glob(os.path.join(d, "*.jpg")) + glob.glob(os.path.join(d, "*.jpeg")))
            if len(imgs) >= 1:
                seqs[os.path.basename(d)] = imgs[:3]
    return seqs


def load_jsonl(path: str):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def save_jsonl(rows, path: str):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def split_by_sequence(ids, val_frac=0.2, seed=0):
    """Hold out WHOLE sequences (all 3 pages stay together), as the task requires."""
    import random
    ids = sorted(ids)
    random.Random(seed).shuffle(ids)
    n_val = max(1, int(len(ids) * val_frac))
    return ids[n_val:], ids[:n_val]
