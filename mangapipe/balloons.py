"""Group OCR lines into balloons / text blocks and compute features for the keep-or-drop classifier.

Idea: every OCR line box is painted white on a 'paper mask' (the text is known, so letters can't break the
balloon), then connected components of white give balloon interiors. Lines that fall in the same
medium-sized component belong to one balloon. Lines on the art (no enclosing balloon) are SFX / signs /
free text and are far more likely to be dropped."""
import re
import cv2
import numpy as np

FEATURES = ["n_lines", "text_len", "n_words", "mean_conf", "alpha_ratio", "upper_ratio", "punct_only",
            "in_balloon", "comp_area_ratio", "comp_fill", "comp_touch_border", "box_w", "box_h",
            "line_h", "cx", "cy", "local_white", "digit_only", "near_edge", "aspect"]


def _paper_mask(gray, lines):
    white = (gray > 205).astype(np.uint8)
    for l in lines:
        x0, y0, x1, y1 = l["box"]
        white[max(0, y0 - 1):y1 + 2, max(0, x0 - 1):x1 + 2] = 1
    return cv2.erode(white, np.ones((3, 3), np.uint8), iterations=1)


def build_groups(img_bgr, lines, min_conf=0.35):
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    lines = [l for l in lines if l["conf"] >= min_conf and l["text"]]
    if not lines:
        return [], dict(H=H, W=W, comp_mask=np.zeros((H, W), np.uint8), gray=gray)
    mask = _paper_mask(gray, lines)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=4)
    balloon_mask = np.zeros((H, W), np.uint8)
    by_comp, free = {}, []
    for i, l in enumerate(lines):
        x0, y0, x1, y1 = l["box"]
        cx, cy = min(W - 1, (x0 + x1) // 2), min(H - 1, (y0 + y1) // 2)
        c = int(lab[cy, cx])
        area = stats[c, cv2.CC_STAT_AREA] if c > 0 else 0
        if c > 0 and area / (H * W) < 0.12:
            by_comp.setdefault(c, []).append(i)
        else:
            free.append(i)
    groups = []

    def make(idxs, comp=None):
        ls = sorted([lines[i] for i in idxs], key=lambda l: (l["box"][1], l["box"][0]))
        x0 = min(l["box"][0] for l in ls); y0 = min(l["box"][1] for l in ls)
        x1 = max(l["box"][2] for l in ls); y1 = max(l["box"][3] for l in ls)
        text = " ".join(l["text"] for l in ls)
        g = dict(lines=ls, box=[x0, y0, x1, y1], text=text, conf=float(np.mean([l["conf"] for l in ls])),
                 comp=comp, line_h=float(np.median([l["box"][3] - l["box"][1] for l in ls])))
        if comp is not None:
            sx, sy, sw, sh, area = [int(v) for v in stats[comp][:5]]
            g["comp_box"] = [sx, sy, sx + sw, sy + sh]
            g["comp_area_ratio"] = area / (H * W)
            g["comp_fill"] = area / max(1, sw * sh)
            g["comp_touch_border"] = float(sx <= 1 or sy <= 1 or sx + sw >= W - 1 or sy + sh >= H - 1)
            balloon_mask[lab == comp] = 1
        else:
            g["comp_box"] = None; g["comp_area_ratio"] = 0.0; g["comp_fill"] = 0.0; g["comp_touch_border"] = 0.0
        g["in_balloon"] = float(comp is not None)
        return g

    for c, idxs in by_comp.items():
        groups.append(make(idxs, c))
    # free lines: merge vertically stacked, horizontally overlapping neighbours into one block
    free.sort(key=lambda i: (lines[i]["box"][1], lines[i]["box"][0]))
    used = set()
    for i in free:
        if i in used:
            continue
        block = [i]; used.add(i)
        changed = True
        while changed:
            changed = False
            bx0 = min(lines[j]["box"][0] for j in block); bx1 = max(lines[j]["box"][2] for j in block)
            by1 = max(lines[j]["box"][3] for j in block)
            for j in free:
                if j in used:
                    continue
                x0, y0, x1, y1 = lines[j]["box"]
                h = y1 - y0
                if 0 <= y0 - by1 <= 0.9 * h and min(bx1, x1) - max(bx0, x0) > 0.3 * min(bx1 - bx0, x1 - x0):
                    block.append(j); used.add(j); changed = True
        groups.append(make(block, None))

    for g in groups:
        g.update(features(g, gray))
    return groups, dict(H=H, W=W, comp_mask=balloon_mask, gray=gray)


def features(g, gray):
    H, W = gray.shape
    x0, y0, x1, y1 = g["box"]
    t = g["text"]
    letters = sum(c.isalpha() for c in t)
    pad = int(0.5 * max(8, g["line_h"]))
    ring = gray[max(0, y0 - pad):min(H, y1 + pad), max(0, x0 - pad):min(W, x1 + pad)]
    return dict(
        n_lines=len(g["lines"]), text_len=len(t), n_words=len(t.split()), mean_conf=g["conf"],
        alpha_ratio=letters / max(1, len(t)), upper_ratio=sum(c.isupper() for c in t) / max(1, letters),
        punct_only=float(letters == 0 and not re.search(r"\d", t)),
        in_balloon=g["in_balloon"], comp_area_ratio=g["comp_area_ratio"], comp_fill=g["comp_fill"],
        comp_touch_border=g["comp_touch_border"], box_w=(x1 - x0) / W, box_h=(y1 - y0) / H,
        line_h=g["line_h"] / H, cx=(x0 + x1) / 2 / W, cy=(y0 + y1) / 2 / H,
        local_white=float((ring > 205).mean()) if ring.size else 0.0,
        digit_only=float(bool(re.fullmatch(r"[\d\s\-.]+", t))),
        near_edge=float(min(y0, H - y1, x0, W - x1) / min(H, W) < 0.06),
        aspect=(x1 - x0) / max(1, y1 - y0),
    )


def heuristic_keep(g):
    """Rule-based fallback used before the classifier is trained (the baseline)."""
    if g["digit_only"] and g["near_edge"]:
        return False
    if g["mean_conf"] < 0.5:
        return False
    if g["in_balloon"]:
        return g["comp_touch_border"] == 0 or g["comp_area_ratio"] < 0.05
    return False
