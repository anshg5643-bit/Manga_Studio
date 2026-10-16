# Fukidashi – run guide

## 1. Install (Python 3.10+)
```
pip install -r requirements.txt
```
No GPU needed for the classic pipeline or the website (about 2–3 s per page on one CPU core).

## 2. Keys → `api_keys.txt`
Open `api_keys.txt`, paste values after the `=`:
- `GOOGLE_CLIENT_ID` – needed for the "Continue with Google" button. In Google Cloud Console, create an OAuth Client ID of type Web application and add both `http://localhost:5000` and `http://127.0.0.1:5000` under Authorized JavaScript origins. Restart Flask after editing this file. The Google button cannot work until this ID and origins are valid.
- `FLASK_SECRET_KEY` – any long random string.
- `HF_TOKEN` – optional, only for downloading Qwen weights.
The task forbids hosted AI inference APIs, so no inference key is used or expected.

## 3. Website
```
python app.py        # http://localhost:5000
```
New visitors get the welcome/sign-up portal once per browser tab session; navigating between features will not repeatedly reopen it. The portal can still be opened manually from Sign up. Accounts live in `instance/users.db`
(passwords hashed with PBKDF2 via werkzeug). Edit `sample_dirs.txt` to point at your dataset folders.
Forgot a password: `python manage.py reset-password you@example.com NewPassword123`.

| Page | What it does |
|---|---|
| `/` `/features` `/how-it-works` | public landing, feature index, explanation |
| `/login` `/signup` `/reset-help` | full sign-in / sign-up pages (the popup does the same) |
| `/analyzer` | upload or load a sequence, edit lines inline, restore rejected blocks, 5 export formats |
| `/speakers` | rename, merge, swap, make narration, re-cluster, click-to-reassign timeline |
| `/reading-order` | direction / weight / panel-cut preview, drag to reorder, reading-path overlay |
| `/batch` | upload a ZIP with 15 sequence folders (3 images per folder), run inference, validate output and download a 15-line `manga_predictions.jsonl` |
| `/evaluate` | proxy scoring of labels vs predictions, per-sequence side-by-side diff |
| `/history` | all saved analyses: search, rename, bulk export/delete |
| `/dashboard` | charts of activity, lines per page, speakers, confidence, top words |
| `/pipeline` | personal defaults, model status, train the keep-filter from labels.jsonl |
| `/account` | profile, password, export data, delete account |

## 4. Dataset scripts
Your zips had **only images** (80 dev + 15 test folders). Put `labels.jsonl` (dev) next to them, then:
```
python scripts/train_filter.py  --seq-root <dev_dir> --labels <labels.jsonl>     # learned text filter
python scripts/tune_harness.py  --seq-root <dev_dir> --labels <labels.jsonl>     # ordering / speaker knobs -> config.json
python scripts/evaluate.py      --seq-root <dev_dir> --labels <labels.jsonl>     # local proxy scorer
python scripts/run_infer.py     --seq-root <test_dir> --out outputs/test_predictions.jsonl [--ids sample_submission.jsonl]
python dataset/score.py --references <labels.jsonl> --predictions <your preds> --output scores.json   # OFFICIAL scorer
```
If `sequences.json` maps ids to images, add `--sequences-json path/to/sequences.json`.

## 5. Optional GPU path (Qwen2.5-VL-3B + LoRA)
```
pip install -r requirements-gpu.txt
python scripts/train_vlm_lora.py --seq-root <dev_dir> --labels <labels.jsonl> --out models/qwen_lora
python scripts/run_infer.py --seq-root <test_dir> --out outputs/test_predictions_vlm.jsonl --backend vlm
```
Set `"backend": "vlm"` in `config.json` to use it from the website.

## Layout
```
app.py  manage.py      Flask server (pages + JSON APIs) and a small user-admin tool
templates/ static/     Jinja pages, theme.css, one JS file per page, common.js
mangapipe/             train.py  ocr.py  balloons.py  textclean.py  classifier.py  order.py  speakers.py  pipeline.py  scoring.py  vlm_backend.py
scripts/               train_filter.py  tune_harness.py  evaluate.py  run_infer.py  train_vlm_lora.py
outputs/               test_predictions.jsonl  (baseline, see README)
```


## ZIP batch upload
On `/batch`, upload one ZIP containing exactly 15 sequence folders. Each sequence folder must contain at least three page images (`.png`, `.jpg`, `.jpeg`, `.webp` or `.bmp`). A common outer wrapper folder is okay. The downloaded `manga_predictions.jsonl` contains one JSON object per line, one line per sequence, in the task's `sequence_id` + `pages` format. Keep page filenames sortable in intended page order (for example `01.png`, `02.png`, `03.png`).
