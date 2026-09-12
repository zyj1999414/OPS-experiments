#!/usr/bin/env python3
import argparse
import importlib.util
import json
import resource
import time
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "algorithms/EFO-Miner.py"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--length", type=int, required=True)
    parser.add_argument("--window", type=int, required=True)
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--minsup", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    raw = np.memmap(args.dataset, dtype="<f8", mode="r")[: args.length]
    spec = importlib.util.spec_from_file_location("original_efo_windows", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    overall_started = time.perf_counter()
    times = []
    frequent_total = 0
    candidates_total = 0
    left = 0
    while left + args.window <= len(raw):
        window = np.asarray(raw[left : left + args.window]).tolist()
        module.read_file = lambda _path, data=window: data
        miner = module.OPRMiner("MEMMAP_WINDOW", str(args.output.parent), min_conf=0.4, min_sup=args.minsup)
        started = time.perf_counter()
        miner.solve()
        times.append(time.perf_counter() - started)
        frequent_total += int(miner.frequent_num)
        candidates_total += int(miner.a + 2)
        left += args.step

    result = {
        "algorithm": "EFO-Miner",
        "dataset": str(args.dataset),
        "data_length": len(raw),
        "window": args.window,
        "step": args.step,
        "minsup": args.minsup,
        "windows": len(times),
        "elapsed_seconds": sum(times),
        "elapsed_wall_seconds": time.perf_counter() - overall_started,
        "window_time_min": min(times),
        "window_time_max": max(times),
        "window_time_mean": sum(times) / len(times),
        "frequent_patterns_total": frequent_total,
        "frequent_patterns_mean": frequent_total / len(times),
        "candidate_patterns_total": candidates_total,
        "candidate_patterns_mean": candidates_total / len(times),
        "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
