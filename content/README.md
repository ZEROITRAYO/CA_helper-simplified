# content/

Static, human-written content shown in the app, one folder per form.

```
content/forms/<FORM>/
  explanation.json   plain-language explanation (filing page, "What is this form?")
  instructions.json  self-filing steps (filing page, "How to file it yourself")
  checklist.json     documents to have ready (filing page checklist)
content/reference/
  gst_states.json    state names and GST codes (state list, GSTIN check, OCR)
  nic_2008.csv       the official NIC activity codes (seed.py)
```

`explanation.json` and `instructions.json` look like this:

```json
{
  "form": "CMP-08",
  "status": "DONE",
  "note": "For writers only, never shown.",
  "title": "How to file CMP-08 yourself",
  "sections": [
    {"heading": "Before you start", "text": ["A paragraph.", "Another paragraph."]},
    {"heading": "Steps", "steps": ["Step 1.", "Step 2."], "text_after": ["A paragraph after the steps."]},
    {"heading": "Common mistakes", "points": ["A bullet point."]},
    {"heading": "Official websites", "links": [{"label": "GST portal", "url": "https://www.gst.gov.in"}]}
  ]
}
```

A section can have `text`, `points`, `steps`, `text_after` and `links`, shown in that order. Write `**bold**` for
bold words. `status` is `TODO` (template), `DRAFT` (written, not checked against the official sources; the app
says so) or `DONE`. `filings.form_content()` turns the two files into the text the filing page shows.

`checklist.json` lists the documents to have ready:

```json
{
  "form": "CMP-08",
  "status": "DONE",
  "note": "For writers only, never shown.",
  "items": [
    {"key": "quarter_turnover", "label": "Your total sales of these 3 months", "required": true,
     "help": "Look in your sales book or your bank passbook"}
  ]
}
```

- `key`: a short snake_case id. **Never rename or remove a key once it is used**: ticks, linked files and the CA's
  document requests are stored against it.
- `label`: the text the user sees.
- `required`: `true` if a CA normally cannot file without it. The filing is "ready" when every required item is
  ticked.
- `help` (optional): a one-line hint under the label.

Rules:
- No legal thresholds, rates or due dates here. They live in DB rule tables and `docs/TODO_VERIFY.md`.
- Cite official sources in the last section of each page.
