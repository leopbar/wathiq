# Quality Lab and Prompt Studio

M5 replaces the evaluation button (which returned seeded data) with measured runs. A run is
finished when the request returns. Results show expected and actual values, dataset/model
versions, build SHA and check counts. Old illustrative history is labelled and excluded from the
summary. These are small diagnostic suites, not production accuracy estimates.

| Band | Coverage | Default checks |
|---|---|---:|
| Model | PDF text reading, classification and exact fields | 50 documents |
| Prompt | Clean golden documents and template contracts | 18 |
| Agent | Bounded repair, critic grounding, review routing and saved corrections | 5 + corrections |
| AI security | Shield, clean control, PII logging, sanitisation and tool allowlist | 6 |
| Adversarial | Invalid/missing dates, bidi controls and distinct Arabic labels | 5 |

The API and CI share the runner. Full workflow/resume/posting coverage remains in integration and
browser tests. Set `WATHIQ_BUILD_SHA` for release attribution; uncommitted local work is `dev`.

## Golden documents

Download golden set returns 50 PDFs and `answer-key.json`: five types, English or bilingual Arabic
labels, and five conditions. Missing-field documents omit one field; cropped documents omit the
bottom half; wrong-type documents contain a cafe receipt. Blurry PDFs are rasterised and blurred
with no hidden text layer. Demo OCR must abstain on them: this does not measure optical recognition.

Answer keys are authored independently of extraction. Arabic labels use embedded DejaVu with
shaping and bidirectional layout. Values are synthetic English test strings; the set does not
establish Arabic-name OCR quality. PDF text reading now uses pypdf instead of a literal-string regex.

## Reviewer corrections

Each new correction snapshots source OCR text, field schema, expected value and task/field key in
the review transaction. For older documents without cached OCR text, capture reads the stored PDF.
Snapshots do not cascade with case deletion and repeated capture is deduplicated. A saved correction
can fail on replay: saving an answer does not train the reader.

Quality Lab replays database snapshots automatically. Export corrections downloads `regressions.json`.
Review the synthetic export and copy it to `backend/app/quality/regressions.json` to include it in CI.
CI cannot read your local database; the checked-in export starts empty. Export before wiping local
volumes. These snapshots retain source values; do not use this workflow for real customer data.

## Prompt versions

The Evaluations tab links template checks and demo-backend correctness to the selected version and
the SHA-256 of its body. Evaluation does not approve or change a pinned version. Old seeded scores
are no longer displayed as linked evidence.

`quality/sensitivity.py` compares original, whitespace and synonym variants, measuring correctness
separately from stability. Tests include a predictor that changes its answer after rewording and
one that always gives the same wrong answer. The demo extractor ignores prompt wording, so live
sensitivity reports unsupported, zero samples and no score. Connecting the harness to Foundry and
running actual wording experiments remains M6 work.

## Calibration and MLflow

Calibration uses approved/corrected human reviews; rejected documents and straight-through cases
do not label untouched fields as correct. Brier uses individual outcomes, not chart-bin averages.
The chart and fitted curve are labelled training diagnostics, not held-out accuracy. A refused
refit cannot leave the database using an older curve while the UI says confidence is raw.

Every fit attempt is recorded locally, including refusals. Enable optional tracking with:

```bash
docker compose --profile ml up -d --build mlflow
```

Click Refit curve and follow the experiment link. MLflow runs as non-root on port 5001 (Conductor
uses 5000), with a persistent SQLite volume. Only aggregate metrics and model/build metadata are
sent. If unavailable, fitting still works and the UI reports tracking unavailable.
Implementation reference: [MLflow REST API](https://mlflow.org/docs/latest/api_reference/rest-api.html).

## CI gate

```bash
docker compose run --rm --no-deps --entrypoint python api -m app.quality.cli
docker compose run --rm --no-deps --entrypoint python api -m app.quality.cli --negative-control
```

Any failing check makes the first command exit 1. The second deliberately corrupts results and
must exit 1; CI verifies that exact code. Each band has a negative control. A separate test replaces
the production extractor with a broken reader and checks that golden cases fail. This proves the
gate detects failures; it does not establish broad real-world coverage.

## M5 interview explanation (five lines)
I built one evaluation runner that works in the Quality Lab and in CI.
It compares synthetic documents with independent answer keys and preserves reviewer corrections.
I tested the gate with deliberately broken results and a broken extractor, so a green result means something.
Prompt results are tied to exact versions; I do not claim wording sensitivity for a reader that ignores prompts.
Calibration reports its training scope and sample count, and MLflow records the fit for comparison.
