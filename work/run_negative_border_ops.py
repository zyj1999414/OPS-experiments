#!/usr/bin/env python3
"""Benchmark the exact negative-border sliding Newsup implementation."""

import argparse
import importlib.util
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np

SOURCE = Path("/Users/zyj/Documents/Codex/2026-08-18/users-zyj-documents-codex-2026-08/sw_newsup_negative_border.py")
NEWSUP_SOURCE = Path("/Users/zyj/Documents/Codex/2026-08-17/qin/outputs/algorithm/newsup.py")
newsup_spec = importlib.util.spec_from_file_location("newsup", NEWSUP_SOURCE)
newsup_module = importlib.util.module_from_spec(newsup_spec)
sys.modules["newsup"] = newsup_module
newsup_spec.loader.exec_module(newsup_module)
spec = importlib.util.spec_from_file_location("sw_newsup_negative_border_bench", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--window", type=int, required=True)
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--minsup", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    values = np.memmap(args.dataset, dtype="<f8", mode="r")
    miner = module.NegativeBorderSlidingNewsup(
        args.window, args.step, args.minsup,
        repair_mode="neighbors", update_mode="batch_halo",
        expire_mode="bincount_lazy",
    )
    started = time.perf_counter()
    result = miner.fit(values)
    windows = 1
    patterns_total = sum(map(len, result))
    while True:
        result = miner.slide(emit=True)
        if result is None:
            break
        windows += 1
        patterns_total += sum(map(len, result))
    elapsed = time.perf_counter() - started
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576
    summary = {
        "algorithm": "NegativeBorderSlidingNewsup",
        "dataset": str(args.dataset), "data_length": len(values),
        "window": args.window, "step": args.step, "minsup": args.minsup,
        "windows": windows, "patterns_total": patterns_total,
        "patterns_mean_per_window": patterns_total / windows,
        "initial_runtime_seconds": miner.initial_runtime,
        "update_runtime_seconds": sum(miner.update_runtimes),
        "elapsed_seconds": elapsed, "peak_rss_mib": peak,
        "levels": len(miner.levels),
        "repair_pair_checks": miner.repair_pair_checks,
        "repair_endpoint_checks": miner.repair_endpoint_checks,
        "normal_new_endpoint_checks": miner.normal_new_endpoint_checks,
        "normal_unique_event_checks": miner.normal_unique_event_checks,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
