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

