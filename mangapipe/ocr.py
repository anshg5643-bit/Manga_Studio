"""Text-line OCR using RapidOCR (open-source, PaddleOCR PP-OCR models exported to ONNX, CPU friendly).
Results are cached on disk by image hash so experiments are fast."""
import hashlib, json, os
import numpy as np

_ENGINE = None
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache", "ocr")


def _engine():
    global _ENGINE
    if _ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR
        _ENGINE = RapidOCR()
    return _ENGINE


def ocr_lines(img_bgr: np.ndarray, use_cache: bool = True):
    """Return list of dict(box=[x0,y0,x1,y1], text, conf) for every detected text line."""
    key = hashlib.sha1(img_bgr.tobytes()).hexdigest()[:20]
    cpath = os.path.join(CACHE_DIR, key + ".json")
    if use_cache and os.path.exists(cpath):
        return json.load(open(cpath))
    res, _ = _engine()(img_bgr)
    lines = []
    for pts, text, conf in (res or []):
        pts = np.array(pts)
        x0, y0 = pts.min(0)
        x1, y1 = pts.max(0)
        lines.append(dict(box=[int(x0), int(y0), int(x1), int(y1)], text=str(text).strip(), conf=float(conf)))
    if use_cache:
        os.makedirs(CACHE_DIR, exist_ok=True)
        json.dump(lines, open(cpath, "w"))
    return lines
