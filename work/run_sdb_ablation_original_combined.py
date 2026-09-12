#!/usr/bin/env python3
"""Benchmark the renamed OPS-Miner and all OPS ablations on SDB1--SDB8."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

ALGORITHMS = [
    "OPS-Miner",
    "-1OPS-Miner",
    "OPS-NoReuse",
    "OPS-NoNumpy",
    "OPS-PF",
    "OPS-Enum",
    "OPS-ISC",
    "OPS-SPF",
    "EFO-OPS",
    "OPF-OPS",
    "SOPP-OPS",
    "OPST-OPS",
]

DATASETS = [
    ("SDB1_GOOG", 1_097, 110, 3),
    ("SDB2_Appliances", 3_947, 395, 3),
    ("SDB3_Beijing_PM25", 8_351, 835, 4),
    ("SDB4_Metro_Traffic", 9_641, 964, 5),
    ("SDB5_OpenAQ_PM25", 2_000, 200, 3),
    ("SDB6_Jena_Temperature", 84_110, 8_411, 42),
    ("SDB7_Berlin_Temperature", 149_026, 14_903, 75),
    ("SDB8_Household_Power", 409_856, 40_986, 205),
]


def command_for(algorithm: str, dataset: Path, metadata: Path, window: int,
                step: int, minsup: int, output: Path) -> list[str]:
    if algorithm == "OPS-Miner":
        runner = ROOT / "work/run_cached_fusion_ops_miner.py"
        return [
            sys.executable, str(runner),
            "--dataset", str(dataset), "--metadata", str(metadata),
            "--window", str(window), "--step", str(step),
            "--minsup", str(minsup), "--output", str(output),
        ]
    runner = ROOT / "work/run_all_ops_algorithm.py"
    return [
        sys.executable, str(runner), f"--algorithm={algorithm}",
        "--dataset", str(dataset), "--metadata", str(metadata),
        "--window", str(window), "--step", str(step),
        "--minsup", str(minsup), "--output", str(output),
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=[f"SDB{i}" for i in range(1, 9)])
    parser.add_argument("--algorithm", choices=ALGORITHMS)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    selected_datasets = DATASETS
    if args.dataset:
        selected_datasets = [x for x in DATASETS if x[0].startswith(args.dataset + "_")]
    selected_algorithms = ALGORITHMS if not args.algorithm else [args.algorithm]

    output_root = ROOT / "outputs/OPS-ablation-SDB1-8-original-combined-overlap90"
    for name, window, step, minsup in selected_datasets:
        dataset = ROOT / "work/sdb1-8-f64" / f"{name}.f64"
        metadata = ROOT / "work/sdb1-8-f64" / f"{name}.json"
        output_dir = output_root / name
        output_dir.mkdir(parents=True, exist_ok=True)
        for algorithm in selected_algorithms:
            output = output_dir / f"{algorithm}.json"
            timeout_output = output_dir / f"{algorithm}.timeout.json"
            error_output = output_dir / f"{algorithm}.error.txt"
            if not args.force and output.exists():
                try:
                    record = json.loads(output.read_text())
                    print("SKIP", name, algorithm, record.get("elapsed_seconds"), flush=True)
                    continue
                except (OSError, json.JSONDecodeError):
                    pass
            started = time.perf_counter()
            print("START", name, algorithm, flush=True)
            try:
                completed = subprocess.run(
                    command_for(algorithm, dataset, metadata, window, step, minsup, output),
                    cwd=ROOT, text=True, capture_output=True, timeout=args.timeout,
                )
            except subprocess.TimeoutExpired as exc:
                elapsed = time.perf_counter() - started
                record = {
                    "algorithm": algorithm, "dataset": name, "status": "timeout",
                    "window": window, "step": step, "minsup": minsup,
                    "timeout_seconds": args.timeout, "elapsed_wall_seconds": elapsed,
                }
                timeout_output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
                stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
                error_output.write_text(stdout + "\n" + stderr)
                print("TIMEOUT", name, algorithm, f"wall={elapsed:.3f}", flush=True)
                continue
            elapsed = time.perf_counter() - started
            if completed.returncode != 0 or not output.exists():
                error_output.write_text(completed.stdout + "\n" + completed.stderr)
                print("ERROR", name, algorithm, completed.returncode,
                      f"wall={elapsed:.3f}", flush=True)
                continue
            record = json.loads(output.read_text())
            print(
                "DONE", name, algorithm,
                f"algorithm={record['elapsed_seconds']:.6f}",
                f"wall={elapsed:.3f}", f"windows={record['windows']}",
                f"patterns={record['patterns_total']}",
                f"rss={record['peak_rss_mib']:.2f}", flush=True,
            )


if __name__ == "__main__":
    main()
