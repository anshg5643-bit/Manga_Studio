"""Qwen2.5-VL (open weights) backend with an optional LoRA adapter trained by scripts/train_vlm_lora.py.
NOTE: written for a GPU box; it was NOT executed in the sandbox this repo was prepared in (CPU only, 3 GB RAM)."""
import json, re
from PIL import Image
import cv2

PROMPT = ("These are three consecutive English manga pages, in order. Extract the story text (dialogue, thoughts, "
          "narration, spoken screams; NOT sound effects, signs, titles, page numbers, notes) in reading order and say "
          "who spoke each line. Use consistent character names across all three pages (char1, char2, ...) and the label "
          "NARRATION only for narrator text. Answer with JSON only: "
          '{"pages":[[{"speaker":"char1","text":"..."}],[...],[...]]}')
_CACHE = {}


def to_pil(im):
    return Image.fromarray(cv2.cvtColor(im, cv2.COLOR_BGR2RGB))


def load(cfg):
    key = (cfg.vlm_base, cfg.vlm_adapter)
    if key not in _CACHE:
        import torch, os
        from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
        model = Qwen2_5_VLForConditionalGeneration.from_pretrained(cfg.vlm_base, torch_dtype=torch.bfloat16, device_map="auto")
        if os.path.isdir(cfg.vlm_adapter):
            from peft import PeftModel
            model = PeftModel.from_pretrained(model, cfg.vlm_adapter)
        proc = AutoProcessor.from_pretrained(cfg.vlm_base, min_pixels=256 * 28 * 28, max_pixels=900 * 28 * 28)
        _CACHE[key] = (model.eval(), proc)
    return _CACHE[key]


def parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    try:
        pages = json.loads(m.group(0))["pages"]
        out = [[dict(speaker=str(l.get("speaker", "char1")), text=str(l.get("text", ""))) for l in p if l.get("text")] for p in pages]
    except Exception:
        out = []
    return (out + [[], [], []])[:3]


def predict(images_bgr, cfg):
    import torch
    model, proc = load(cfg)
    pil = [to_pil(i) for i in images_bgr]
    msgs = [{"role": "user", "content": [{"type": "image"}] * len(pil) + [{"type": "text", "text": PROMPT}]}]
    prompt = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    enc = proc(text=[prompt], images=pil, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**enc, max_new_tokens=1800, do_sample=False)
    return parse(proc.batch_decode(out[:, enc.input_ids.shape[1]:], skip_special_tokens=True)[0])
