"""Cheap OCR post-processing learned from looking at errors on the dev pages (see README for the list)."""
import re
import wordninja

_DIGIT_FIX = str.maketrans({"0": "O", "1": "I", "5": "S", "6": "G", "8": "B"})
_LM = wordninja.DEFAULT_LANGUAGE_MODEL
_CONTR = re.compile(r"(?i)(n't|'s|'re|'ll|'m|'ve|'d)(?=[A-Za-z]{2,})")


def _known(w):
    return w.lower() in _LM._wordcost


def _fix_token(tok):
    m = re.match(r"^([^A-Za-z0-9']*)(.*?)([^A-Za-z0-9']*)$", tok)
    pre, core, post = m.groups()
    if not core:
        return tok
    fixed_digits = False
    if re.search(r"[A-Za-z]", core) and re.search(r"\d", core):
        core = core.translate(_DIGIT_FIX); fixed_digits = True   # S01 -> SOI, I60t -> IGOt
    core = _CONTR.sub(lambda mm: mm.group(1) + " ", core)   # ISN'THE -> ISN'T HE
    words = []
    for part in core.split(" "):
        base = part.replace("'", "")
        if base.isalpha() and not _known(base) and "'" not in part and (len(base) >= 5 or (fixed_digits and len(base) >= 3)):
            words += wordninja.split(part)          # MELIKE -> ME LIKE, GIRLWHO -> GIRL WHO
        else:
            words.append(part)
    return pre + " ".join(words) + post


def clean(text):
    t = " ".join(_fix_token(t) for t in text.split())
    t = re.sub(r"(?<!\.)\.{2}(?!\.)", "...", t)   # ".." -> "..."
    t = re.sub(r"\.{4,}", "...", t)                    # "...." -> "..."
    return re.sub(r"\s+", " ", t).strip()
