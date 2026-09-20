"""`python -m app.quality.cli`: fail CI on any diagnostic regression.

--negative-control deliberately corrupts results and MUST exit 1. No database required.
"""

import argparse
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from app.db.enums import QualityBand
from app.quality.suites import run_band


async def main(broken: bool) -> int:
    failed = 0
    # Export reviewed synthetic examples from /quality/regressions/export into this file
    # to share the exact same snapshots with CI. The live UI also replays database examples.
    snapshots = json.loads(Path(__file__).with_name("regressions.json").read_text())
    regressions = [SimpleNamespace(**snapshot) for snapshot in snapshots]
    for band in QualityBand:
        results = await run_band(band, broken=broken, regressions=regressions)
        failures = [r.row() for r in results if not r.passed]
        failed += len(failures)
        print(
            json.dumps(
                {
                    "band": band,
                    "sample_count": len(results),
                    "failed": len(failures),
                    "failures": failures,
                },
                ensure_ascii=False,
            )
        )
    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.negative_control)))
