# Implemented changes

- Batch page accepts a ZIP upload containing exactly 15 sequence folders.
- Each sequence folder can contain three page images directly or in a nested folder. PNG, JPG, JPEG, WEBP and BMP are supported.
- ZIP extraction only writes image files, rejects path traversal, and caps extracted image data at 250 MB.
- Uploaded ZIP inference always processes all 15 sequences, regardless of the local-folder limit field.
- Download is named `manga_predictions.jsonl`; it contains one JSON object per line in the task's `sequence_id` and `pages` schema.
- Sign-up portal auto-opens once per browser tab session, rather than on every feature navigation. Users can still open it manually.
- Added feature entrance, card, navigation and button animations with reduced-motion accessibility support.
- Google Identity Services setup remains supported. Google OAuth must use a valid Web application Client ID and have both `http://localhost:5000` and `http://127.0.0.1:5000` configured as authorized JavaScript origins.

## ZIP layout

Recommended:

```text
manga_sequences.zip
  seq_001/
    01.png
    02.png
    03.png
  seq_002/
    01.png
    02.png
    03.png
  ...
  seq_015/
    01.png
    02.png
    03.png
```

A single common wrapper folder around all 15 sequence folders is also supported. Keep filenames sortable in intended page order.
