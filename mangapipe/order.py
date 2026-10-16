"""Reading order from balloon geometry.

Ink-based panel detection fails on manga because panels often touch full-bleed art, so instead we run an
XY-cut on the *balloon boxes*: split into tiers wherever a horizontal band crosses no balloon, otherwise into
columns where a vertical band crosses none; recurse. Tiers read top->bottom, columns right->left (manga).
When nothing can be cut, fall back to a tunable score  alpha*y + (1-x)  (top-right first)."""


def _box(g):
    return g["comp_box"] if g.get("comp_box") else g["box"]


def _split(groups, axis, gap):
    """Split groups along axis (1 = by y -> tiers, 0 = by x -> columns) wherever the projection has a gap."""
    items = sorted(groups, key=lambda g: _box(g)[axis])
    parts, cur, end = [], [items[0]], _box(items[0])[axis + 2]
    for g in items[1:]:
        b = _box(g)
        if b[axis] - end >= gap:
            parts.append(cur); cur = [g]; end = b[axis + 2]
        else:
            cur.append(g); end = max(end, b[axis + 2])
    parts.append(cur)
    return parts


def _fallback(groups, W, H, rtl, alpha):
    def key(g):
        b = _box(g)
        cx, cy = (b[0] + b[2]) / 2 / W, (b[1] + b[3]) / 2 / H
        return alpha * cy + ((1 - cx) if rtl else cx)
    return sorted(groups, key=key)


def _cut(groups, W, H, rtl, alpha, gap, depth=0):
    if len(groups) <= 1 or depth > 6:
        return list(groups)
    for axis in (1, 0):  # tiers first, then columns
        parts = _split(groups, axis, gap)
        if len(parts) > 1:
            if axis == 0 and rtl:
                parts = parts[::-1]
            out = []
            for p in parts:
                out += _cut(p, W, H, rtl, alpha, gap, depth + 1)
            return out
    return _fallback(groups, W, H, rtl, alpha)


def order_groups(groups, gray, rtl=True, alpha=1.0, use_panels=True):
    H, W = gray.shape
    if not groups:
        return []
    out = _cut(groups, W, H, rtl, alpha, gap=max(4, int(0.004 * H))) if use_panels else _fallback(groups, W, H, rtl, alpha)
    for i, g in enumerate(out):
        g["order"] = i
    return out
