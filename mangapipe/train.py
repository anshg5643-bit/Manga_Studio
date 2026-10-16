"""Train the keep-filter. Used by scripts/train_filter.py and by the website's Pipeline page."""
import numpy as np
from rapidfuzz import fuzz
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import GroupKFold
from sklearn.metrics import f1_score, precision_score, recall_score
from . import ocr, balloons, classifier, textclean, scoring


def train_filter(seqs, refs, progress=None, save=True):
    """seqs: id -> [img paths]; refs: id -> pages (labels). Positive block = fuzzy match (>=80) to a labelled line."""
    from .pipeline import _read
    X, y, grp, base = [], [], [], []
    ids = [i for i in refs if i in seqs]
    for k, sid in enumerate(ids):
        for pi, ref in enumerate(refs[sid][:3]):
            im = _read(seqs[sid][pi])
            groups, _ = balloons.build_groups(im, ocr.ocr_lines(im))
            for g in groups:
                t = scoring.norm(textclean.clean(g["text"]))
                best = max([fuzz.partial_ratio(t, scoring.norm(r["text"])) if len(t) > 3 else fuzz.ratio(t, scoring.norm(r["text"])) for r in ref] or [0])
                X.append(classifier.vec(g)); y.append(int(best >= 80)); grp.append(sid); base.append(int(balloons.heuristic_keep(g)))
        if progress:
            progress(k + 1, len(ids))
    if len(set(y)) < 2:
        raise ValueError("Labels matched no text blocks (or only matched one class). Check that sequence ids match the image folders.")
    X, y, grp, base = np.array(X), np.array(y), np.array(grp), np.array(base)
    mk = lambda: GradientBoostingClassifier(n_estimators=150, max_depth=3, learning_rate=0.08, random_state=0)
    oof = np.zeros(len(y))
    for tr, te in GroupKFold(min(5, len(set(grp))) if len(set(grp)) > 1 else 2).split(X, y, grp) if len(set(grp)) > 1 else []:
        oof[te] = mk().fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    sc = lambda p: dict(precision=float(precision_score(y, p, zero_division=0)), recall=float(recall_score(y, p, zero_division=0)), f1=float(f1_score(y, p, zero_division=0)))
    rep = dict(n_sequences=len(ids), n_blocks=int(len(y)), pos_rate=float(y.mean()), rule_baseline=sc(base),
               learned_cv=sc(oof > .5) if len(set(grp)) > 1 else None)
    if save:
        classifier.save(mk().fit(X, y), dict(features=balloons.FEATURES, cv=rep))
    return rep
