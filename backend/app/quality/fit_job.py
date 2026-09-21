"""The calibration fit, as a script an Azure ML command job runs.

`python -m app.quality.fit_job --samples '[[0.9,true],...]' --model-version demo-extractor-1.0.0`

Deliberately thin. It parses its arguments, calls the *same* `calibration.fit()` the API calls
in process, and writes the result to `outputs/curve/curve.json`. There is no second
implementation of Platt scaling anywhere in this repository, because two implementations of a
calibration curve eventually disagree and then nobody knows which one scored a case.

It has no database access and no settings dependency, so it runs on a bare compute instance
with nothing but the application package installed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.agent.calibration import fit

# Where Azure ML collects a job's named output. The job definition in `app/azure/ml.py` asks
# for the output called `curve`, and this is where that output has to be written.
OUTPUT_DIR = Path("outputs/curve")


def parse_samples(raw: str) -> list[tuple[float, bool]]:
    """`[[0.91, true], [0.42, false]]` → the pairs `fit()` expects.

    Anything malformed raises here, in the job, where the failure is attributed to the input
    rather than surfacing later as a curve that quietly fitted on fewer points than intended.
    """
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError("--samples must be a JSON array")

    samples: list[tuple[float, bool]] = []
    for index, item in enumerate(parsed):
        if not isinstance(item, list | tuple) or len(item) != 2:
            raise ValueError(f"sample {index} is not a [score, correct] pair")
        samples.append((float(item[0]), bool(item[1])))
    return samples


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fit Wathiq's confidence calibration curve.")
    parser.add_argument("--samples", required=True, help="JSON array of [score, correct] pairs")
    parser.add_argument("--model-version", default="", help="the extractor version fitted on")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    args = parser.parse_args(argv)

    samples = parse_samples(args.samples)
    curve = fit(samples, model_version=args.model_version)

    body = curve.as_dict()
    # `as_dict()` is shaped for the UI. The two Brier scores are what the "do no harm" guard
    # needs on the way back, so they are written explicitly rather than assumed to be there.
    body["brier_before"] = curve.brier_before
    body["brier_after"] = curve.brier_after
    body["a"] = curve.a
    body["b"] = curve.b

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "curve.json").write_text(json.dumps(body, indent=2), encoding="utf-8")

    print(
        f"fitted={curve.fitted} samples={curve.sample_count} "
        f"brier {curve.brier_before:.4f} -> {curve.brier_after:.4f}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - entry point
    raise SystemExit(main())
