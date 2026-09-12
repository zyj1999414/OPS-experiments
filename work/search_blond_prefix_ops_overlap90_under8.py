#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "work/run_all_ops_algorithm.py"
DATA = ROOT / "OPS-data-main9/06_power_blond250/06_power_blond250_256MiB.f64"
OUT = ROOT / "outputs/blond-prefix-ops-overlap90-search"
LENGTHS = {"SDB61_1": 65_536, "SDB68_8": 524_288}
WINDOWS = (30_000, 35_000, 40_000, 42_000, 43_000)
MINSUPS = (2, 4, 8, 20, 40, 80, 160)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def measure(name, length, window, minsup):
    step = window // 10
    count = (length - window) // step + 1
    metadata = OUT / "metadata" / f"{name}.json"
    save(metadata, {"boundaries": [{"start": 0, "length": length}]})
    result = OUT / "runs" / f"w{window}-m{minsup}-{name}.json"
    command = [
        sys.executable, str(RUNNER), "--algorithm", "OPS-Miner",
        "--dataset", str(DATA), "--metadata", str(metadata),
        "--window", str(window), "--step", str(step), "--minsup", str(minsup),
        "--max-windows", str(count), "--output", str(result),
    ]
    subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    return json.loads(result.read_text())


def main():
    rows = []
    for window in WINDOWS:
        for minsup in MINSUPS:
            small = measure("SDB61_1", LENGTHS["SDB61_1"], window, minsup)
            large = measure("SDB68_8", LENGTHS["SDB68_8"], window, minsup)
            ratio = large["elapsed_seconds"] / small["elapsed_seconds"]
            row = {
                "window": window, "step": window // 10, "overlap": 0.9,
                "minsup": minsup, "small_windows": small["windows"],
                "large_windows": large["windows"],
                "small_seconds": small["elapsed_seconds"],
                "large_seconds": large["elapsed_seconds"], "ratio": ratio,
                "small_patterns_mean": small["patterns_mean_per_window"],
                "large_patterns_mean": large["patterns_mean_per_window"],
            }
            rows.append(row)
            print(window, minsup, row["small_windows"], row["large_windows"], ratio, flush=True)
    rows.sort(key=lambda row: row["ratio"])
    save(OUT / "summary.json", rows)
    print("BEST", json.dumps(rows[0], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
