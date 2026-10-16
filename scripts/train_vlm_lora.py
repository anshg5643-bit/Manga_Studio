"""LoRA fine-tune Qwen2.5-VL-3B-Instruct on the dev sequences: 3 page images -> JSON of (speaker, text) per page.
Sequence-level validation split. Needs a GPU (>=24 GB with gradient checkpointing). UNTESTED in the build sandbox.

pip install -r requirements-gpu.txt
python scripts/train_vlm_lora.py --seq-root dev_dir --labels labels.jsonl --epochs 3 --out models/qwen_lora"""
import argparse, json, os, sys, random, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import torch
from PIL import Image
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
from peft import LoraConfig, get_peft_model
from mangapipe.data import load_sequences, load_jsonl, split_by_sequence
from mangapipe.vlm_backend import PROMPT

ap = argparse.ArgumentParser()
ap.add_argument("--seq-root", required=True); ap.add_argument("--sequences-json")
ap.add_argument("--labels", required=True); ap.add_argument("--base", default="Qwen/Qwen2.5-VL-3B-Instruct")
ap.add_argument("--out", default="models/qwen_lora"); ap.add_argument("--epochs", type=int, default=3)
ap.add_argument("--lr", type=float, default=1e-4); ap.add_argument("--accum", type=int, default=4)
ap.add_argument("--val-frac", type=float, default=0.15); ap.add_argument("--max-pixels", type=int, default=700 * 28 * 28)
a = ap.parse_args()

random.seed(0); torch.manual_seed(0)
refs = {r["sequence_id"]: r["pages"] for r in load_jsonl(a.labels)}
seqs = load_sequences(a.seq_root, a.sequences_json)
tr_ids, va_ids = split_by_sequence(list(refs), a.val_frac)
proc = AutoProcessor.from_pretrained(a.base, min_pixels=256 * 28 * 28, max_pixels=a.max_pixels)
model = Qwen2_5_VLForConditionalGeneration.from_pretrained(a.base, torch_dtype=torch.bfloat16, device_map="auto")
model.gradient_checkpointing_enable(); model.enable_input_require_grads()
model = get_peft_model(model, LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM",
        target_modules=r".*model\.language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)"
        if hasattr(model, "model") and hasattr(model.model, "language_model") else ["q_proj", "k_proj", "v_proj", "o_proj"]))
model.print_trainable_parameters()


def encode(sid):
    pil = [Image.open(p).convert("RGB") for p in seqs[sid]]
    msgs = [{"role": "user", "content": [{"type": "image"}] * len(pil) + [{"type": "text", "text": PROMPT}]}]
    prompt = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    answer = json.dumps({"pages": refs[sid]}, ensure_ascii=False) + "<|im_end|>"
    full = proc(text=[prompt + answer], images=pil, return_tensors="pt")
    n_prompt = proc(text=[prompt], images=pil, return_tensors="pt").input_ids.shape[1]
    labels = full.input_ids.clone(); labels[:, :n_prompt] = -100
    return {k: v.to(model.device) for k, v in full.items()}, labels.to(model.device)


def run_loss(sid):
    enc, labels = encode(sid)
    return model(**enc, labels=labels).loss


params = [p for p in model.parameters() if p.requires_grad]
opt = torch.optim.AdamW(params, lr=a.lr, weight_decay=0.0)
steps_total = a.epochs * len(tr_ids) // a.accum
sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / 5) * max(0.05, 1 - s / max(1, steps_total)))
log = []
for ep in range(a.epochs):
    model.train(); random.shuffle(tr_ids); run, t0 = 0.0, time.time()
    for i, sid in enumerate(tr_ids):
        loss = run_loss(sid) / a.accum; loss.backward(); run += loss.item() * a.accum
        if (i + 1) % a.accum == 0:
            torch.nn.utils.clip_grad_norm_(params, 1.0); opt.step(); sched.step(); opt.zero_grad()
    model.eval()
    with torch.no_grad():
        vl = sum(run_loss(s).item() for s in va_ids) / max(1, len(va_ids))
    log.append(dict(epoch=ep + 1, train_loss=run / len(tr_ids), val_loss=vl, secs=time.time() - t0)); print(log[-1], flush=True)
    model.save_pretrained(a.out)
os.makedirs("outputs", exist_ok=True)
json.dump(dict(log=log, train_ids=tr_ids, val_ids=va_ids), open("outputs/train_vlm_log.json", "w"), indent=2)
