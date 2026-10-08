# eval/

Evaluation datasets and scripts for the report (X3). **Never real personal data**: synthetic or fully
anonymised data only (fake names, fake but correctly formatted PAN/GSTIN, no real addresses or phone numbers).

| Folder | Measures | Evaluates module | Data |
|---|---|---|---|
| `ocr/` | OCR field accuracy on sample documents | documents (DO8, DO9), onboarding (ON13) | 15 made-up documents, 74 fields |

Each folder's README describes its file format. Each script (`eval/<folder>/evaluate.py`) calls the **same service
functions as the app** and prints a small results table; `eval/common.py` holds the shared helpers (the import
path, the app context, the table). Run them in the backend container (`docker compose up` first):

```bash
docker compose exec backend python ../eval/ocr/evaluate.py                       # no database needed
```

The datasets were labelled by Claude (`labelled_by` / `created_by`
`claude`) and should be checked by a teammate before the numbers go into the report.

## Results (29 Sep 2026)

| Evaluation | Result |
|---|---|
| OCR (all local) | 95.9% of fields (71/74): text PDF 96.0%, photo 100%, scanned PDF 91.7%. Misses: a TDS "Provisional Receipt" is not recognised as an acknowledgement (2 documents), and Tesseract cut one scanned token number short. |
