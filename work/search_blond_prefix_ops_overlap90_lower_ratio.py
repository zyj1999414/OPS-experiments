#!/usr/bin/env python3
import json
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "work/run_all_ops_algorithm.py"
DATA = ROOT / "OPS-data-main9/06_power_blond250/06_power_blond250_256MiB.f64"
OUT = ROOT / "outputs/blond-prefix-ops-overlap90-lower-ratio-search"
ENDPOINTS = [("small", 65_536), ("large", 524_288)]
WINDOWS = (10_000, 15_000, 20_000, 25_000, 30_000, 35_000, 40_000, 42_000, 43_000)
MINSUPS = (40, 80, 120, 160, 240, 320, 500, 800, 1_000)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def measure(tag, length, window, minsup, repeat):
    step = window // 10
    windows = (length - window) // step + 1
    metadata = OUT / "metadata" / f"{tag}.json"
    save(metadata, {"boundaries": [{"start": 0, "length": length}]})
    result = OUT / "runs" / f"w{window}-m{minsup}-{tag}-r{repeat}.json"
    command = [
        sys.executable, str(RUNNER), "--algorithm", "OPS-Miner",
        "--dataset", str(DATA), "--metadata", str(metadata),
        "--window", str(window), "--step", str(step), "--minsup", str(minsup),
        "--max-windows", str(windows), "--output", str(result),
    ]
    subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    return json.loads(result.read_text())


def main():
    rows = []
    for window in WINDOWS:
        for minsup in MINSUPS:
            measured = {}
            for tag, length in ENDPOINTS:
                runs = [measure(tag, length, window, minsup, repeat) for repeat in range(1, 4)]
                measured[tag] = {
                    "seconds": statistics.median(r["elapsed_seconds"] for r in runs),
                    "windows": runs[0]["windows"],
                    "patterns_mean": runs[0]["patterns_mean_per_window"],
                }
            ratio = measured["large"]["seconds"] / measured["small"]["seconds"]
            row = {"window": window, "step": window // 10, "minsup": minsup,
                   "overlap": 0.9, "ratio": ratio, **measured}
            rows.append(row)
            print(window, minsup, f"{ratio:.4f}", measured["small"]["patterns_mean"], flush=True)
    meaningful = [r for r in rows if r["small"]["patterns_mean"] >= 20]
    meaningful.sort(key=lambda r: r["ratio"])
    save(OUT / "summary.json", {"all": rows, "meaningful_sorted": meaningful})
    print("BEST", json.dumps(meaningful[0], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
