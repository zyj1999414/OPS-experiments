#!/usr/bin/env python3
import json
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "work/run_all_ops_algorithm.py"
DATA = ROOT / "OPS-data-main9/06_power_blond250/06_power_blond250_256MiB.f64"
OUT = ROOT / "outputs/blond-prefix-ops-overlap90-w10000-m40-verified"
WINDOW = 10_000
STEP = 1_000
MINSUP = 40


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def main():
    rows = []
    for scale in range(1, 9):
        name = f"SDB6{scale}_{scale}"
        length = scale * 65_536
        windows = (length - WINDOW) // STEP + 1
        metadata = OUT / "metadata" / f"{name}.json"
        save(metadata, {"boundaries": [{"start": 0, "length": length}]})
        trials = []
        rss = []
        patterns = []
        for repeat in range(1, 6):
            result = OUT / "trials" / name / f"run{repeat}.json"
            command = [
                sys.executable, str(RUNNER), "--algorithm", "OPS-Miner",
                "--dataset", str(DATA), "--metadata", str(metadata),
                "--window", str(WINDOW), "--step", str(STEP),
                "--minsup", str(MINSUP), "--max-windows", str(windows),
                "--output", str(result),
            ]
            subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
            measured = json.loads(result.read_text())
            trials.append(measured["elapsed_seconds"])
            rss.append(measured["peak_rss_mib"])
            patterns.append(measured["patterns_total"])
        row = {
            "dataset": name, "data_length": length, "window": WINDOW,
            "step": STEP, "overlap": 0.9, "minsup": MINSUP, "windows": windows,
            "runtime_trials": trials, "runtime_median": statistics.median(trials),
            "peak_rss_mib_median": statistics.median(rss),
            "patterns_total": patterns[0], "patterns_mean": patterns[0] / windows,
        }
        rows.append(row)
        print("DONE", name, windows, row["runtime_median"], flush=True)
    ratio = rows[-1]["runtime_median"] / rows[0]["runtime_median"]
    save(OUT / "summary.json", {"results": rows, "endpoint_runtime_ratio": ratio})
    print("RATIO", ratio, flush=True)


if __name__ == "__main__":
    main()
