#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "work/run_all_ops_algorithm.py"
DATA = ROOT / "OPS-data-main9/06_power_blond250/06_power_blond250_256MiB.f64"
OUT = ROOT / "outputs/blond-two-scalability-all-ablation"
ALGORITHMS = [
    "OPS-SPF", "OPS-ISC", "OPS-PF", "OPS-Enum", "OPS-NoReuse",
    "EFO-OPS", "OPF-OPS", "SOPP-OPS", "OPST-OPS", "OPS-Miner",
]
SINGLE = [(mib, mib * 131_072) for mib in range(4, 33, 4)]
STREAM_WINDOW = 524_288
STREAM_STEP = 52_429
STREAM = [(k, STREAM_WINDOW + (k - 1) * STREAM_STEP) for k in (5, 10, 15, 20, 25)]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def run(algorithm, experiment, label, length, window, step, minsup, windows):
    result = OUT / experiment / algorithm / f"{label}.json"
    if result.exists():
        print("SKIP", experiment, algorithm, label, flush=True)
        return
    result.parent.mkdir(parents=True, exist_ok=True)
    metadata = OUT / "metadata" / f"{experiment}-{label}.json"
    save(metadata, {"boundaries": [{"start": 0, "length": length}]})
    pending = result.with_suffix(".pending.json")
    command = [
        sys.executable, str(RUNNER), "--algorithm", algorithm,
        "--dataset", str(DATA), "--metadata", str(metadata),
        "--window", str(window), "--step", str(step), "--minsup", str(minsup),
        "--max-windows", str(windows), "--output", str(pending),
    ]
    print("START", experiment, algorithm, label, flush=True)
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    result.with_suffix(".log").write_text(completed.stdout + "\n" + completed.stderr)
    if completed.returncode:
        print("FAILED", experiment, algorithm, label, completed.returncode, flush=True)
        return
    pending.replace(result)
    measured = json.loads(result.read_text())
    print(
        "DONE", experiment, algorithm, label,
        f"{measured['elapsed_seconds']:.6f}s",
        f"{measured['peak_rss_mib']:.2f}MiB",
        measured["patterns_total"],
        flush=True,
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for algorithm in ALGORITHMS:
        for mib, points in SINGLE:
            run(algorithm, "C1", f"{mib}MiB", points, points, points, 1000, 1)
    for algorithm in ALGORITHMS:
        for windows, length in STREAM:
            run(algorithm, "C2", f"K{windows}", length, STREAM_WINDOW, STREAM_STEP, 1000, windows)
    print("ALL_DONE", flush=True)


if __name__ == "__main__":
    main()
