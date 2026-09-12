#!/usr/bin/env python3
"""Run the local WOPP-Miner and emit benchmark statistics as JSON."""

import argparse
import importlib.util
import json
import resource
import time
from pathlib import Path

import numpy as np

SOURCE = Path("/Users/zyj/Documents/Codex/2026-08-17/qin/work/input/algorithm/4thWOPP-Miner_副本.py")
spec = importlib.util.spec_from_file_location("wopp_miner_benchmark_source", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--window", type=int, required=True)
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--minsup", type=int, required=True)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--prefix", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.dataset.suffix.lower() == ".f64":
        data = np.memmap(args.dataset, dtype="<f8", mode="r")
    else:
        data = module.read_numeric_series(args.dataset)
    if args.prefix is not None:
        series = [data[:args.prefix]]
    elif args.metadata is not None:
        metadata = json.loads(args.metadata.read_text())
        boundaries = metadata.get("boundaries") or []
        series = [data[item["start"]:item["start"] + item["length"]]
                  for item in boundaries] if boundaries else [data]
    else:
        series = [data]
    started = time.perf_counter()
    results = []
    for values in series:
        miner = module.WindowOPRMinerOptimized(
            window_len=args.window, step=args.step, min_sup=args.minsup
        )
        results.extend(miner.run(values))
    elapsed = time.perf_counter() - started
    windows = len(results)
    patterns_total = sum(sum(level_counts) for level_counts in results)
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576
    summary = {
        "algorithm": "WOPP-Miner", "dataset": str(args.dataset),
        "data_length": len(data), "source_series": len(series),
        "window": args.window, "step": args.step,
        "minsup": args.minsup, "windows": windows,
        "patterns_total": patterns_total,
        "patterns_mean_per_window": patterns_total / windows if windows else None,
        "elapsed_seconds": elapsed, "peak_rss_mib": peak,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
