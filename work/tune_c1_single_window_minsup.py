#!/usr/bin/env python3
import json
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "work/run_all_ops_algorithm.py"
DATA = ROOT / "OPS-data-main9/06_power_blond250/06_power_blond250_256MiB.f64"
OUT = ROOT / "outputs/c1-single-window-minsup-tuning"
MINSUPS = (40, 80, 160, 320, 500, 1_000, 2_000, 4_000, 8_000, 16_000)
ENDPOINTS = (("4MiB", 524_288), ("32MiB", 4_194_304))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def main():
    rows = []
    for minsup in MINSUPS:
        endpoint = {}
        for label, points in ENDPOINTS:
            metadata = OUT / "metadata" / f"{label}.json"
            save(metadata, {"boundaries": [{"start": 0, "length": points}]})
            runs = []
            for repeat in range(1, 6):
                result = OUT / "runs" / f"m{minsup}-{label}-r{repeat}.json"
                command = [
                    sys.executable, str(RUNNER), "--algorithm", "OPS-Miner",
                    "--dataset", str(DATA), "--metadata", str(metadata),
                    "--window", str(points), "--step", str(points),
                    "--minsup", str(minsup), "--max-windows", "1", "--output", str(result),
                ]
                subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
                runs.append(json.loads(result.read_text()))
            endpoint[label] = {
                "runtime_median": statistics.median(r["elapsed_seconds"] for r in runs),
                "peak_rss_mib_median": statistics.median(r["peak_rss_mib"] for r in runs),
                "patterns": runs[0]["patterns_total"],
            }
        ratio = endpoint["32MiB"]["runtime_median"] / endpoint["4MiB"]["runtime_median"]
        row = {"minsup": minsup, **endpoint, "ratio": ratio}
        rows.append(row)
        print("DONE", minsup, ratio, endpoint["4MiB"]["patterns"], endpoint["32MiB"]["patterns"], flush=True)
    save(OUT / "summary.json", rows)


if __name__ == "__main__":
    main()
