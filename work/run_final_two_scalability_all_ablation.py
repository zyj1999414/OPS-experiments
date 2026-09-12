#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "work/run_all_ops_algorithm.py"
DATA = ROOT.parent / "data/SDB8/06_power_blond250_256MiB.f64"
OUT = ROOT / "outputs/final-two-scalability-all-ablation"
ALGORITHMS = [
    "OPS-SPF", "OPS-ISC", "OPS-PF", "OPS-Enum", "OPS-NoReuse",
    "EFO-OPS", "OPF-OPS", "SOPP-OPS", "OPST-OPS", "OPS-Miner",
]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def run_one(experiment, label, algorithm, length, window, step, minsup, windows):
    result = OUT / experiment / algorithm / f"{label}.json"
    if result.exists():
        print("SKIP", experiment, algorithm, label, flush=True)
        return
    metadata = OUT / "metadata" / f"{experiment}-{label}.json"
    save(metadata, {"boundaries": [{"start": 0, "length": length}]})
    pending = result.with_suffix(".pending.json")
    result.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, str(RUNNER), "--algorithm", algorithm,
        "--dataset", str(DATA), "--metadata", str(metadata),
        "--window", str(window), "--step", str(step), "--minsup", str(minsup),
        "--max-windows", str(windows), "--count-candidates", "--output", str(pending),
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
        measured["patterns_total"], flush=True,
    )


def main():
    c1 = [(f"{mib}MiB", mib * 131_072) for mib in range(4, 33, 4)]
    c2 = [(f"SDB6{i}_{i}", i * 65_536) for i in range(1, 9)]
    for algorithm in ALGORITHMS:
        for label, points in c1:
            run_one("C1", label, algorithm, points, points, points, 2_000, 1)
    for algorithm in ALGORITHMS:
        for label, points in c2:
            windows = (points - 10_000) // 1_000 + 1
            run_one("C2", label, algorithm, points, 10_000, 1_000, 40, windows)
    print("ALL_DONE", flush=True)


if __name__ == "__main__":
    main()
