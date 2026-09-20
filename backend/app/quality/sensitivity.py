"""Prompt-aware backend harness. Demo mode explicitly cannot supply this backend.

One observation is a document/variant pair. Stability and correctness are separate: a
model can give the same wrong answer every time. The caller must supply authored answers.
"""
from collections.abc import Awaitable, Callable

from app.quality.suites import Result, wording_variants

Predict = Callable[[str, str], Awaitable[dict]]


async def measure(body: str, fixtures: list[dict], predict: Predict) -> list[Result]:
    results = []
    for fixture in fixtures:
        outputs = [await predict(variant, fixture["text"]) for variant in wording_variants(body)]
        for index, output in enumerate(outputs):
            results.append(Result(f"{fixture['key']}: correctness variant {index}",
                                  fixture["expected"], output))
            if index:
                results.append(Result(f"{fixture['key']}: stability variant {index}",
                                      outputs[0], output))
    return results
