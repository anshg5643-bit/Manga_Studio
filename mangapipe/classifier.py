"""Learned 'is this block story text?' filter (the part of the CPU pipeline that is trained on the dev labels).
Gradient boosting over cheap geometric / OCR features; falls back to rules when no model file exists."""
import os, pickle
import numpy as np
from .balloons import FEATURES, heuristic_keep

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "keep_filter.pkl")
_MODEL = {}


def vec(g):
    return [float(g[f]) for f in FEATURES]


def load(path=DEFAULT_PATH):
    if path not in _MODEL:
        _MODEL[path] = pickle.load(open(path, "rb")) if os.path.exists(path) else None
    return _MODEL[path]


def keep_probs(groups, path=DEFAULT_PATH):
    m = load(path)
    if m is None:
        return [1.0 if heuristic_keep(g) else 0.0 for g in groups], False
    if not groups:
        return [], True
    X = np.array([vec(g) for g in groups])
    return list(m["clf"].predict_proba(X)[:, 1]), True


def save(clf, meta, path=DEFAULT_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pickle.dump(dict(clf=clf, meta=meta), open(path, "wb"))
    _MODEL.pop(path, None)
