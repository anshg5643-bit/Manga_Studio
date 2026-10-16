"""End-to-end orchestration + overlay rendering. Backends:  classic (OCR+learned filter)  |  vlm (Qwen2.5-VL LoRA)."""
import base64, os
from dataclasses import dataclass, asdict
import cv2
import numpy as np

from . import ocr, balloons, order, speakers, classifier, textclean

PALETTE = [(255, 75, 47), (47, 150, 255), (40, 190, 120), (240, 170, 20), (170, 80, 230), (20, 200, 210)]


@dataclass
class PipelineConfig:
    backend: str = "classic"       # classic | vlm
    keep_threshold: float = 0.5     # classifier probability threshold
    rtl: bool = True                # manga reading direction
    alpha: float = 1.0              # weight of vertical position in in-panel ordering
    use_panels: bool = True
    speaker_mode: str = "alternate"  # alternate | appearance | single
    speaker_thr: float = 0.35
    vlm_adapter: str = "models/qwen_lora"
    vlm_base: str = "Qwen/Qwen2.5-VL-3B-Instruct"

    @staticmethod
    def from_file(path):
        import json
        cfg = PipelineConfig()
        if os.path.exists(path):
            for k, v in json.load(open(path)).items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
        return cfg


def _read(img):
    if isinstance(img, np.ndarray):
        return img
    if isinstance(img, (bytes, bytearray)):
        return cv2.imdecode(np.frombuffer(img, np.uint8), cv2.IMREAD_COLOR)
    arr = np.fromfile(img, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _classic(images, cfg):
    pages_groups, ctxs, used_model, rejected = [], [], False, []
    for im in images:
        lines = ocr.ocr_lines(im)
        groups, ctx = balloons.build_groups(im, lines)
        probs, used_model = classifier.keep_probs(groups)
        for g, p in zip(groups, probs):
            g["p_keep"] = float(p)
        for g in groups:
            g["text"] = textclean.clean(g["text"])
        kept = [g for g in groups if g["p_keep"] >= cfg.keep_threshold and g["text"]]
        kept = order.order_groups(kept, ctx["gray"], rtl=cfg.rtl, alpha=cfg.alpha, use_panels=cfg.use_panels)
        rejected.append([dict(text=g["text"], p_keep=round(g["p_keep"], 3), box=g["comp_box"] or g["box"])
                         for g in groups if g["text"] and g["p_keep"] < cfg.keep_threshold])
        pages_groups.append(kept); ctxs.append(ctx)
    speakers.assign(pages_groups, ctxs, cfg.speaker_mode, cfg.speaker_thr)
    return pages_groups, ctxs, used_model, rejected


def render_overlay(img, kept, max_w=900):
    out = img.copy()
    names = {}
    for g in kept:
        c = (60, 60, 60) if g["speaker"] == "NARRATION" else PALETTE[names.setdefault(g["speaker"], len(names)) % len(PALETTE)]
        x0, y0, x1, y1 = g["comp_box"] if g.get("comp_box") else g["box"]
        cv2.rectangle(out, (x0, y0), (x1, y1), c, 3)
        label = f'{g["order"] + 1}'
        cv2.circle(out, (x0, y0), 16, c, -1)
        cv2.putText(out, label, (x0 - 7 - 4 * (len(label) - 1), y0 + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
    h, w = out.shape[:2]
    if w > max_w:
        out = cv2.resize(out, (max_w, int(h * max_w / w)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode()


def analyze_sequence(images, cfg: PipelineConfig = None, overlay=False):
    cfg = cfg or PipelineConfig()
    imgs = [_read(i) for i in images]
    if cfg.backend == "vlm":
        from . import vlm_backend
        pages = vlm_backend.predict(imgs, cfg)
        detail = [[dict(speaker=l["speaker"], text=l["text"], order=i + 1, p_keep=1.0, box=None) for i, l in enumerate(p)] for p in pages]
        return dict(pages=pages, config=asdict(cfg), used_trained_filter=None, overlays=[], detail=detail,
                    rejected=[[], [], []], sizes=[[im.shape[1], im.shape[0]] for im in imgs])
    pages_groups, ctxs, used_model, rejected = _classic(imgs, cfg)
    pages = [[dict(speaker=g["speaker"], text=g["text"]) for g in gs] for gs in pages_groups]
    detail = [[dict(speaker=g["speaker"], text=g["text"], order=g["order"] + 1, p_keep=round(g["p_keep"], 3),
                    box=g["comp_box"] or g["box"]) for g in gs] for gs in pages_groups]
    res = dict(pages=pages, detail=detail, config=asdict(cfg), used_trained_filter=used_model, rejected=rejected,
               sizes=[[im.shape[1], im.shape[0]] for im in imgs])
    res["overlays"] = [render_overlay(im, gs) for im, gs in zip(imgs, pages_groups)] if overlay else []
    return res


def render_overlay_detail(img, detail, rejected=None, show_rejected=True, max_w=900):
    """Draw numbered boxes from a (possibly user-edited) detail list: [{speaker,text,order,box}]."""
    out = img.copy()
    names = {}
    if show_rejected:
        for r in rejected or []:
            x0, y0, x1, y1 = r["box"]
            cv2.rectangle(out, (x0, y0), (x1, y1), (150, 150, 150), 2, cv2.LINE_AA)
    for d in sorted(detail, key=lambda d: d["order"]):
        if not d.get("box"):
            continue
        sp = d["speaker"]
        c = (60, 60, 60) if sp == "NARRATION" else PALETTE[names.setdefault(sp, len(names)) % len(PALETTE)]
        x0, y0, x1, y1 = d["box"]
        cv2.rectangle(out, (x0, y0), (x1, y1), c, 3)
        label = str(d["order"])
        cv2.circle(out, (x0, y0), 16, c, -1)
        cv2.putText(out, label, (x0 - 7 - 4 * (len(label) - 1), y0 + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
    h, w = out.shape[:2]
    if w > max_w:
        out = cv2.resize(out, (max_w, int(h * max_w / w)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return buf.tobytes()
