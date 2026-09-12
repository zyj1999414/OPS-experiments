#!/usr/bin/env python3
import json
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "work/run_all_ops_algorithm.py"
DATA = ROOT / "OPS-data-main9/06_power_blond250/06_power_blond250_256MiB.f64"
OUT = ROOT / "outputs/c1-single-window-minsup2000-verified"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def main():
    rows = []
    for mib in range(4, 33, 4):
        points = mib * 131_072
        metadata = OUT / "metadata" / f"{mib}MiB.json"
        save(metadata, {"boundaries": [{"start": 0, "length": points}]})
        runs = []
        for repeat in range(1, 6):
            result = OUT / "trials" / f"{mib}MiB-r{repeat}.json"
            command = [
                sys.executable, str(RUNNER), "--algorithm", "OPS-Miner",
                "--dataset", str(DATA), "--metadata", str(metadata),
                "--window", str(points), "--step", str(points),
                "--minsup", "2000", "--max-windows", "1", "--output", str(result),
            ]
            subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
            runs.append(json.loads(result.read_text()))
        row = {
            "size_mib": mib, "data_points": points, "window": points,
            "windows": 1, "minsup": 2000,
            "runtime_trials": [r["elapsed_seconds"] for r in runs],
            "runtime_median": statistics.median(r["elapsed_seconds"] for r in runs),
            "peak_rss_mib_median": statistics.median(r["peak_rss_mib"] for r in runs),
            "patterns_total": runs[0]["patterns_total"],
        }
        rows.append(row)
        print("DONE", mib, row["runtime_median"], row["patterns_total"], flush=True)
    ratio = rows[-1]["runtime_median"] / rows[0]["runtime_median"]
    save(OUT / "summary.json", {"results": rows, "endpoint_runtime_ratio": ratio})
    print("RATIO", ratio, flush=True)


if __name__ == "__main__":
    main()
