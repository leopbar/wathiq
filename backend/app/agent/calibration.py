"""Confidence calibration.

A model that says "90% sure" should be right about 90% of the time. Raw scores almost never
behave like that — they are usually over-confident — so the raw number is mapped through a
curve fitted on outcomes we actually observed.

**Where the outcomes come from.** Every field a reviewer looked at is a labelled example: a
field they accepted was right, a field they corrected was wrong. That is free, continuously
growing ground truth, and it is what `fit_from_outcomes` uses. In M5 the golden dataset adds
labelled examples that no human had to produce.

**The method: Platt scaling.** One logistic curve, two parameters:

    calibrated = 1 / (1 + exp(-(a · raw + b)))

Fitted by gradient descent on log loss. Two parameters cannot overfit a few hundred examples,
and — the reason it matters here — the shape is explainable to an auditor in one sentence:
"we learned how much to trust the extractor's own score, and applied that correction".

Written by hand rather than with scikit-learn: it is forty lines, it keeps a 300 MB numeric
stack out of the API image, and it stays deterministic. Isotonic regression and MLflow
tracking arrive in M5 with the golden set, where the extra flexibility has enough data to be
worth it. See DECISIONS.md.

**Before it is fitted**, the identity curve is used and `fitted` is false everywhere in the
UI. An uncalibrated number is shown as raw, never dressed up as calibrated.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

# Gradient descent settings. Fixed and deterministic — no randomness anywhere, so the same
# data always produces the same curve.
#
# The first version of this used 400 steps at a rate of 0.5 and stopped well short of the
# minimum: the curve it produced scored *worse* than doing nothing, the guard below caught it,
# and calibration silently never turned on. Two thousand steps at 1.0 converges on a few
# hundred examples in a few milliseconds, and `_TOLERANCE` stops early once the gradient is
# negligible so a larger dataset does not cost more than it needs to.
_ITERATIONS = 2000
_LEARNING_RATE = 1.0
_TOLERANCE = 1e-7
# Platt's own smoothing: instead of targets 0 and 1, use values a little inside the range, so
# a small sample cannot drive the curve to infinity.
_MIN_SAMPLES = 20


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exponent = math.exp(value)
    return exponent / (1.0 + exponent)


@dataclass(slots=True)
class CalibrationCurve:
    """The fitted mapping from a raw score to a calibrated probability."""

    a: float = 1.0
    b: float = 0.0
    fitted: bool = False
    sample_count: int = 0
    brier_before: float = 0.0
    brier_after: float = 0.0
    model_version: str = ""

    def apply(self, raw: float) -> float:
        """Map one raw score. An unfitted curve returns the raw score unchanged."""
        if not self.fitted:
            return round(max(0.0, min(1.0, raw)), 3)
        return round(max(0.0, min(1.0, _sigmoid(self.a * raw + self.b))), 3)

    @property
    def improvement(self) -> float:
        """How much the Brier score improved. Negative would mean calibration made it worse."""
        return round(self.brier_before - self.brier_after, 4)

    def as_dict(self) -> dict[str, Any]:
        return {
            "a": round(self.a, 4),
            "b": round(self.b, 4),
            "fitted": self.fitted,
            "sample_count": self.sample_count,
            "brier_before": round(self.brier_before, 4),
            "brier_after": round(self.brier_after, 4),
            "improvement": self.improvement,
            "model_version": self.model_version,
        }


IDENTITY = CalibrationCurve()


def _brier(samples: list[tuple[float, bool]], curve: CalibrationCurve) -> float:
    """Mean squared error between the stated probability and what happened. Lower is better."""
    if not samples:
        return 0.0
    total = sum((curve.apply(raw) - (1.0 if correct else 0.0)) ** 2 for raw, correct in samples)
    return total / len(samples)


def fit(samples: list[tuple[float, bool]], *, model_version: str = "") -> CalibrationCurve:
    """Fit the curve on (raw score, was it correct) pairs.

    Returns the identity curve when there is too little data. Refusing to fit is the honest
    answer to twelve examples; a curve fitted on twelve points would look authoritative and be
    meaningless.
    """
    usable = [(max(0.0, min(1.0, raw)), bool(correct)) for raw, correct in samples]
    if len(usable) < _MIN_SAMPLES:
        # The sample count is reported even when the fit is refused, so the UI can say
        # "not enough data yet" with a number instead of an empty shrug.
        return CalibrationCurve(model_version=model_version, sample_count=len(usable))

    positives = sum(1 for _raw, correct in usable if correct)
    negatives = len(usable) - positives
    if positives == 0 or negatives == 0:
        # Everything was right, or everything was wrong. There is no curve to learn from that.
        return CalibrationCurve(model_version=model_version, sample_count=len(usable))

    # Platt's target smoothing, which keeps the parameters finite on a small sample.
    high = (positives + 1.0) / (positives + 2.0)
    low = 1.0 / (negatives + 2.0)

    a, b = 1.0, 0.0
    count = float(len(usable))
    for _step in range(_ITERATIONS):
        grad_a = 0.0
        grad_b = 0.0
        for raw, correct in usable:
            target = high if correct else low
            predicted = _sigmoid(a * raw + b)
            error = predicted - target
            grad_a += error * raw
            grad_b += error
        step_a = _LEARNING_RATE * grad_a / count
        step_b = _LEARNING_RATE * grad_b / count
        a -= step_a
        b -= step_b
        if abs(step_a) < _TOLERANCE and abs(step_b) < _TOLERANCE:
            break

    fitted = CalibrationCurve(
        a=a,
        b=b,
        fitted=True,
        sample_count=len(usable),
        model_version=model_version,
    )
    fitted.brier_before = _brier(usable, IDENTITY)
    fitted.brier_after = _brier(usable, fitted)

    if fitted.brier_after > fitted.brier_before:
        # The fit made things worse. Keep the raw scores and say the curve is not fitted,
        # rather than shipping a curve that is worse than doing nothing.
        return CalibrationCurve(model_version=model_version, sample_count=len(usable))
    return fitted


@dataclass(slots=True)
class ReliabilityBin:
    """One bar of the reliability chart: 'when we said ~80%, we were right 73% of the time'."""

    predicted: float
    observed: float
    n: int = 0


def reliability(
    samples: list[tuple[float, bool]], curve: CalibrationCurve | None = None, bins: int = 10
) -> list[ReliabilityBin]:
    """Group the samples into bins and compare stated confidence with what happened."""
    curve = curve or IDENTITY
    buckets: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    for raw, correct in samples:
        probability = curve.apply(raw)
        index = min(bins - 1, max(0, int(probability * bins)))
        buckets[index].append((probability, correct))

    points: list[ReliabilityBin] = []
    for bucket in buckets:
        if not bucket:
            continue
        predicted = sum(probability for probability, _ in bucket) / len(bucket)
        observed = sum(1 for _, correct in bucket if correct) / len(bucket)
        points.append(
            ReliabilityBin(
                predicted=round(predicted, 3),
                observed=round(observed, 3),
                n=len(bucket),
            )
        )
    return points


@dataclass
class CalibrationState:
    """The process-wide active curve.

    Held in memory and refreshed from the database at startup and after a refit, so the hot
    path (one call per extracted field) never touches the database.
    """

    curve: CalibrationCurve = field(default_factory=CalibrationCurve)

    def set(self, curve: CalibrationCurve) -> None:
        self.curve = curve

    def apply(self, raw: float) -> float:
        return self.curve.apply(raw)


_state = CalibrationState()


def active() -> CalibrationCurve:
    return _state.curve


def set_active(curve: CalibrationCurve) -> None:
    _state.set(curve)


def calibrate(raw: float) -> float:
    """The one function the pipeline calls."""
    return _state.apply(raw)
