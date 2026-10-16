# BYTE Applied ML – The Manga Task

> **This README is a skeleton. The task says to write it yourself, in your own words – so I only filled in
> facts about the code. Replace every `TODO` with what *you* did, saw and decided.** (How to run: `RUN_GUIDE.md`.)

## 1. Who did what (be specific – this is graded)
- Code in this repo was **drafted by an AI assistant (Claude)** at your request. TODO: list what *you* wrote,
  changed, debugged, chose, or ran. TODO: external code/models you used (RapidOCR / PaddleOCR PP-OCR weights,
  wordninja, scikit-learn, Qwen2.5-VL, Flask, Google Identity Services).

## 2. Approach (what the code does – verify you understand each step)
1. **OCR**: RapidOCR returns text lines + boxes.
2. **Balloons**: line boxes are painted white on a thresholded page; connected white components = balloons.
   Lines in the same component are joined. Lines on art stay as "free" blocks.
3. **Keep filter (the learned part)**: gradient-boosted trees over 20 geometric/OCR features decide
   story text vs SFX / page numbers / signs. Trained on dev labels with sequence-level GroupKFold.
   Before training, a hand-written rule is the baseline.
4. **Text cleanup**: word splitting (`MELIKE` → `ME LIKE`), digit/letter fixes, ellipsis normalisation.
5. **Reading order**: XY-cut on balloon boxes (tiers top→bottom, columns right→left), fallback score tunable by `alpha`.
6. **Speakers**: baseline only – alternating char1/char2, or clustering of a tiny grey-level descriptor of nearby art,
   rectangular tail-less boxes → `NARRATION`.
7. **Optional**: Qwen2.5-VL-3B + LoRA (`scripts/train_vlm_lora.py`) mapping 3 pages → JSON.

## 3. State of the results – read before you submit
- `outputs/test_predictions.jsonl` was produced by the **untrained baseline** (rule filter, no tuning) because the
  uploaded zips contained **no labels, no sequences.json, no score.py and no sample_submission.jsonl**.
  It is not a trained result. Sequence ids are the folder names; page order is assumed to be `01,02,03`.
- No dev score exists yet. `mangapipe/scoring.py` is **my own proxy** of the two metrics, not the official scorer.
- The Qwen LoRA code **was never run** (build sandbox: CPU, 3 GB RAM). Expect to debug it on your GPU.
- The website was tested through Flask's test client (every page renders, every API exercised) and its JS passes a syntax check, but I had no browser, so **check the UI, animations and Google button in your own browser**.
- TODO: after you add labels, fill in this table with real numbers from the official `score.py`:

| System | text_order_score | balanced_joint_f1 | notes |
|---|---|---|---|
| Rule filter + alternate speakers | TODO | TODO | baseline |
| + trained filter | TODO | TODO | |
| + tuned ordering/speakers | TODO | TODO | |
| Qwen2.5-VL-3B zero-shot | TODO | TODO | |
| Qwen2.5-VL-3B + LoRA | TODO | TODO | |

## 4. Known weaknesses (observed on a few dev pages)
- Punctuation-only balloons (`...`, `?!`) are often missed by OCR – the task counts them.
- Speaker labelling is the weakest part; "alternate" breaks when one character speaks twice in a row.
- OCR confuses 1/I, 0/O and drops dots; some of this is patched in `textclean.py`.
- Narration detection is a shape rule and will mislabel rectangular balloons.

## 5. What I would try next (TODO: your own ideas)
Balloon-tail → nearest-character linking, face/character re-identification embeddings, a manga-trained text detector,
fine-tuning the VLM on OCR-balloon crops instead of full pages, balloon-connection graphs for odd layouts.
