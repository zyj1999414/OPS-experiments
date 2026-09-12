#!/usr/bin/env python3
"""Run OPS-Miner independently within source-series boundaries."""

import argparse
import importlib.util
import json
import resource
import time
from pathlib import Path

import numpy as np


SOURCE = Path("/Users/zyj/Documents/Codex/2026-08-18/users-zyj-documents-codex-2026-08/OPS-ablation/OPS-Miner.py")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--window", type=int, required=True)
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--minsup", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    spec = importlib.util.spec_from_file_location("ops_miner_user", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    values = np.memmap(args.dataset, dtype="<f8", mode="r")
    metadata = json.loads(args.metadata.read_text())
    # Most inputs are one continuous series.  Multi-record inputs such as
    # Kepler explicitly provide boundaries so windows never cross records.
    boundaries = metadata.get("boundaries") or [{"start": 0, "length": len(values)}]
    windows = patterns_total = 0
    patterns_min = patterns_max = None
    started = time.perf_counter()
    for boundary in boundaries:
        start = int(boundary["start"])
        length = int(boundary["length"])
        if length < args.window:
            continue
        miner = module.L2IncrementalPPCNewsup(args.window, args.step, args.minsup)
        result = miner.find2(values[start : start + length])
        while result is not None:
            count = int(sum(map(len, result)))
            windows += 1
            patterns_total += count
            patterns_min = count if patterns_min is None else min(patterns_min, count)
            patterns_max = count if patterns_max is None else max(patterns_max, count)
            result = miner.find2()

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    summary = {
        "algorithm": "OPS-Miner",
        "dataset": str(args.dataset),
        "data_length": len(values),
        "source_series": len(boundaries),
        "window": args.window,
        "step": args.step,
        "minsup": args.minsup,
        "windows": windows,
        "patterns_total": patterns_total,
        "patterns_min": patterns_min,
        "patterns_max": patterns_max,
        "patterns_mean_per_window": patterns_total / windows if windows else None,
        "elapsed_seconds": time.perf_counter() - started,
        "peak_rss_bytes": peak,
        "peak_rss_mib": peak / 1048576,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
