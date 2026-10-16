# Manga Studio

A web-based workspace for manga image analysis, panel editing, and sequence processing.

**Live Demo:** https://mangastudio-production.up.railway.app

## Features
- Manga image analysis and processing
- Panel and sequence management
- Editing and reviewing analysis results
- Batch processing and evaluation tools
- User authentication with optional Google Sign-In

## Tech Stack
- Python and Flask
- HTML, CSS and JavaScript
- SQLite
- Railway deployment

## Configuration
Some features require Google OAuth credentials or model access tokens. Configure these through environment variables or the application's supported configuration files. Never commit API keys or secrets to GitHub.

## External Code and Model References
- [Flask](https://flask.palletsprojects.com/)
- [Python](https://docs.python.org/3/)
- [SQLite](https://www.sqlite.org/docs.html)
- [Railway](https://docs.railway.com/)
- [Google Identity Services](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid)
- [Hugging Face Hub](https://huggingface.co/docs/hub/model-cards) — for model documentation, if applicable.

Any third-party code or pretrained models included in the project should be credited with their original repository, licence, and model details.

## Notes
Analysis results depend on the input images and the configured processing pipeline. Generated predictions should be validated before being used as final annotations.

## License
Specify the project licence and comply with the licences of all third-party dependencies and models.

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
