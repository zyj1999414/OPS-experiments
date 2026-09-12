#!/usr/bin/env python3
import json
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "work/run_all_ops_algorithm.py"
DATA = ROOT / "OPS-data-main9/06_power_blond250/06_power_blond250_256MiB.f64"
OUT = ROOT / "outputs/blond-prefix-ops-under8"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def main():
    summary = []
    for scale in range(1, 9):
        name = f"SDB6{scale}_{scale}"
        length = scale * 65_536
        metadata = OUT / "metadata" / f"{name}.json"
        save(metadata, {"boundaries": [{"start": 0, "length": length}]})
        trials = []
        rss = []
        patterns = []
        for repeat in range(1, 6):
            result = OUT / "trials" / name / f"run{repeat}.json"
            cmd = [
                sys.executable, str(RUNNER), "--algorithm", "OPS-Miner",
                "--dataset", str(DATA), "--metadata", str(metadata),
                "--window", "65536", "--step", "65536", "--minsup", "80",
                "--max-windows", str(scale), "--output", str(result),
            ]
            done = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True)
            measured = json.loads(result.read_text())
            trials.append(measured["elapsed_seconds"])
            rss.append(measured["peak_rss_mib"])
            patterns.append(measured["patterns_total"])
        row = {
            "dataset": name, "data_length": length, "window": 65_536,
            "step": 65_536, "overlap": 0, "minsup": 80, "windows": scale,
            "runtime_trials": trials, "runtime_median": statistics.median(trials),
            "peak_rss_mib_median": statistics.median(rss),
            "patterns_total": patterns[0],
        }
        summary.append(row)
        print("DONE", name, row["runtime_median"], flush=True)
    ratio = summary[-1]["runtime_median"] / summary[0]["runtime_median"]
    save(OUT / "summary.json", {"results": summary, "endpoint_runtime_ratio": ratio})
    print("RATIO", ratio, flush=True)


if __name__ == "__main__":
    main()
