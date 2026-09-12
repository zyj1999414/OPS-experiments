#!/usr/bin/env python3
"""Benchmark three miners on SDB4--SDB8 with about 100 windows at 90% overlap."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "work/sdb1-8-f64"
ALGORITHMS = ("Original-Combined", "OPS-NoReuse", "WOPP-Miner")
DATASETS = (
    ("SDB4_Metro_Traffic", 4_422, 442, 3),
    ("SDB5_OpenAQ_PM25", 914, 91, 3),
    ("SDB6_Jena_Temperature", 38_583, 3_858, 19),
    ("SDB7_Berlin_Temperature", 68_360, 6_836, 34),
    ("SDB8_Household_Power", 188_005, 18_800, 94),
)


def command_for(name: str, dataset: Path, metadata: Path, window: int,
                step: int, minsup: int, output: Path):
    common = [
        "--dataset", str(dataset), "--window", str(window),
        "--step", str(step), "--minsup", str(minsup), "--output", str(output),
    ]
    if name == "Original-Combined":
        return [
            sys.executable, str(ROOT / "work/run_cached_fusion_ops_miner.py"),
            *common[:2], "--metadata", str(metadata), *common[2:],
        ]
    if name == "OPS-NoReuse":
        return [
            sys.executable, str(ROOT / "work/run_all_ops_algorithm.py"),
            "--algorithm", name, *common[:2], "--metadata", str(metadata),
            *common[2:],
        ]
    return [sys.executable, str(ROOT / "work/run_wopp_miner_benchmark.py"), *common]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "outputs/SDB4-8-three-algorithms-windows100-overlap90.json",
    )
    args = parser.parse_args()
    summaries = []
    with tempfile.TemporaryDirectory() as temporary:
        temporary_dir = Path(temporary)
        for dataset_name, window, step, minsup in DATASETS:
            dataset = DATA_ROOT / f"{dataset_name}.f64"
            metadata = DATA_ROOT / f"{dataset_name}.json"
            runs = {name: [] for name in ALGORITHMS}
            status = {name: "complete" for name in ALGORITHMS}
            for repetition in range(args.repetitions):
                order = list(ALGORITHMS)
                shift = repetition % len(order)
                order = order[shift:] + order[:shift]
                for name in order:
                    if status[name] != "complete":
                        continue
                    output = temporary_dir / f"{dataset_name}-{name}-{repetition}.json"
                    started = time.perf_counter()
                    try:
                        subprocess.run(
                            command_for(name, dataset, metadata, window, step, minsup, output),
                            cwd=ROOT, check=True, capture_output=True, text=True,
                            timeout=args.timeout,
                        )
                    except subprocess.TimeoutExpired:
                        status[name] = f"timeout after {time.perf_counter() - started:.1f}s"
                        print(dataset_name, name, status[name], flush=True)
                        continue
                    result = json.loads(output.read_text())
                    runs[name].append(result)
                    print(
                        dataset_name, name, repetition + 1,
                        f"{result['elapsed_seconds']:.6f}s", flush=True,
                    )
            algorithms = {}
            for name in ALGORITHMS:
                if not runs[name]:
                    algorithms[name] = {"status": status[name]}
                    continue
                times = [item["elapsed_seconds"] for item in runs[name]]
                rss = [item["peak_rss_mib"] for item in runs[name]]
                algorithms[name] = {
                    "status": status[name], "completed_runs": len(runs[name]),
                    "times_seconds": times,
                    "median_seconds": statistics.median(times),
                    "peak_rss_mib_values": rss,
                    "median_peak_rss_mib": statistics.median(rss),
                    "windows": runs[name][0]["windows"],
                    "patterns_total": runs[name][0]["patterns_total"],
                    "patterns_mean_per_window": runs[name][0]["patterns_mean_per_window"],
                }
            summary = {
                "dataset": dataset_name, "data_length": dataset.stat().st_size // 8,
                "window": window, "step": step, "overlap": 1 - step / window,
                "minsup": minsup, "target_windows": 100,
                "algorithms": algorithms,
            }
            if all("median_seconds" in algorithms[name] for name in ALGORITHMS):
                reuse = algorithms["Original-Combined"]["median_seconds"]
                summary["reuse_speedup_vs_noreuse"] = (
                    algorithms["OPS-NoReuse"]["median_seconds"] / reuse
                )
                summary["reuse_speedup_vs_wopp"] = (
                    algorithms["WOPP-Miner"]["median_seconds"] / reuse
                )
            summaries.append(summary)
            print(json.dumps(summary, ensure_ascii=False), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summaries, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
