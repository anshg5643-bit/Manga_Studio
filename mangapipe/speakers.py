"""Speaker labelling baselines (CPU, no labels needed). These are deliberately simple and are the weakest
part of the classic pipeline - the Qwen2.5-VL LoRA backend (scripts/train_vlm_lora.py) is the intended upgrade.

modes
  alternate   : two characters talk in turn (char1, char2, char1, ...) continuing across the 3 pages
  appearance  : describe the art around each balloon with a tiny grey-level descriptor and cluster across pages
  single      : everything is char1 (sanity floor)
Rectangular, box-like text blocks that sit away from characters are labelled NARRATION."""
import cv2
import numpy as np


def is_narration(g, ctx=None):
    if g["in_balloon"] and g["comp_fill"] > 0.93 and g["comp_area_ratio"] < 0.08 and g["aspect"] > 1.0:
        return True
    return False


def _descriptor(g, gray, bmask):
    H, W = gray.shape
    x0, y0, x1, y1 = g["comp_box"] or g["box"]
    mx, my = int(0.9 * (x1 - x0)), int(0.9 * (y1 - y0))
    a0, b0, a1, b1 = max(0, x0 - mx), max(0, y0 - my), min(W, x1 + mx), min(H, y1 + my)
    win = gray[b0:b1, a0:a1].astype(np.float32)
    ok = bmask[b0:b1, a0:a1] == 0
    px = win[ok]
    if px.size < 50:
        return np.zeros(11, np.float32)
    hist, _ = np.histogram(px, bins=8, range=(0, 256))
    hist = hist / hist.sum()
    edges = cv2.Canny(win.astype(np.uint8), 80, 160)[ok].mean() / 255
    return np.concatenate([hist, [px.mean() / 255, px.std() / 255, edges]]).astype(np.float32)


def assign(pages_groups, pages_ctx, mode="alternate", thr=0.35, max_chars=4):
    """pages_groups: list (3) of kept groups already in reading order. Mutates g['speaker']."""
    flat = [(pi, g) for pi, gs in enumerate(pages_groups) for g in gs]
    for _, g in flat:
        g["narr"] = is_narration(g)
    chars = [(pi, g) for pi, g in flat if not g["narr"]]
    if mode == "single" or not chars:
        for _, g in chars:
            g["speaker"] = "char1"
    elif mode == "alternate":
        for i, (_, g) in enumerate(chars):
            g["speaker"] = f"char{1 + i % 2}"
    else:
        from sklearn.cluster import AgglomerativeClustering
        D = np.stack([_descriptor(g, pages_ctx[pi]["gray"], pages_ctx[pi]["comp_mask"]) for pi, g in chars])
        if len(chars) == 1:
            labels = [0]
        else:
            labels = AgglomerativeClustering(n_clusters=None, distance_threshold=thr, linkage="average").fit_predict(D)
            # cap number of characters: merge extras into the largest clusters
            counts = np.bincount(labels)
            keep = list(np.argsort(-counts)[:max_chars])
            if len(counts) > max_chars:
                cent = {k: D[labels == k].mean(0) for k in keep}
                labels = [l if l in keep else min(keep, key=lambda k: np.linalg.norm(D[i] - cent[k])) for i, l in enumerate(labels)]
        remap = {}
        for l in labels:
            remap.setdefault(l, f"char{len(remap) + 1}")
        for (_, g), l in zip(chars, labels):
            g["speaker"] = remap[l]
    for _, g in flat:
        if g["narr"]:
            g["speaker"] = "NARRATION"
