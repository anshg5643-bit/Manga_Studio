"""LOCAL PROXY scorer. The official dataset/score.py was not included in the uploaded zips, so these metrics are
my own approximation of 'text_order_score' and 'balanced_joint_f1'. Use them to compare experiments with each
other, then confirm with the official score.py."""
import re
import numpy as np
from rapidfuzz import fuzz
from scipy.optimize import linear_sum_assignment


def norm(t):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s.!?…-]", "", t.lower())).strip()


def match(pred, ref, thr=60):
    """one-to-one greedy fuzzy matching of lines on one page -> list of (pred_idx, ref_idx)"""
    cands = sorted(((fuzz.ratio(norm(p["text"]), norm(r["text"])), i, j)
                    for i, p in enumerate(pred) for j, r in enumerate(ref)), reverse=True)
    up, ur, out = set(), set(), []
    for s, i, j in cands:
        if s < thr:
            break
        if i in up or j in ur:
            continue
        up.add(i); ur.add(j); out.append((i, j, s / 100))
    return out


def order_agreement(pairs):
    if len(pairs) < 2:
        return 1.0
    pairs = sorted(pairs, key=lambda p: p[1])
    seq = [p[0] for p in pairs]
    conc = sum(1 for a in range(len(seq)) for b in range(a + 1, len(seq)) if seq[a] < seq[b])
    tot = len(seq) * (len(seq) - 1) / 2
    return conc / tot


def score_sequence(pred_pages, ref_pages):
    n_pred = sum(len(p) for p in pred_pages); n_ref = sum(len(p) for p in ref_pages)
    sim_sum, matched, agree_w = 0.0, [], []
    for pi, (pp, rr) in enumerate(zip(pred_pages, ref_pages)):
        m = match(pp, rr)
        sim_sum += sum(s for _, _, s in m)
        matched += [(pi, i, j, pp[i]["speaker"], rr[j]["speaker"]) for i, j, _ in m]
        agree_w.append((order_agreement([(i, j) for i, j, _ in m]), len(m)))
    prec = sim_sum / n_pred if n_pred else (1.0 if n_ref == 0 else 0.0)
    rec = sim_sum / n_ref if n_ref else 1.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    tw = sum(w for _, w in agree_w)
    order = sum(a * w for a, w in agree_w) / tw if tw else (1.0 if n_ref == 0 else 0.0)
    text_order = f1 * order
    # speaker identity: best one-to-one mapping pred speaker -> ref speaker over matched lines
    ps = sorted({m[3] for m in matched}); rs = sorted({m[4] for m in matched})
    joint = 0.0
    if matched:
        C = np.zeros((len(ps), len(rs)))
        for _, _, _, a, b in matched:
            C[ps.index(a), rs.index(b)] += 1
        r_i, c_i = linear_sum_assignment(-C)
        mp = {ps[a]: rs[b] for a, b in zip(r_i, c_i)}
        correct = sum(1 for _, _, _, a, b in matched if mp.get(a) == b)
        jp = correct / n_pred if n_pred else 0.0
        jr = correct / n_ref if n_ref else 0.0
        joint = 2 * jp * jr / (jp + jr) if jp + jr else 0.0
    return dict(text_order_score=text_order, text_f1=f1, order_agreement=order, balanced_joint_f1=joint,
                n_pred=n_pred, n_ref=n_ref)


def score_all(preds, refs):
    """preds/refs: dict id -> pages. Sequences with no text in the reference are skipped from the mean."""
    rows = {sid: score_sequence(preds.get(sid, [[], [], []]), refs[sid]) for sid in refs}
    use = [r for r in rows.values() if r["n_ref"] > 0] or list(rows.values())
    mean = {k: float(np.mean([r[k] for r in use])) for k in ("text_order_score", "text_f1", "order_agreement", "balanced_joint_f1")}
    return mean, rows
