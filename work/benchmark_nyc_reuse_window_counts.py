#!/usr/bin/env python3
"""Compare Original-Combined and OPS-NoReuse at 90% overlap on NYC."""

from __future__ import annotations

import argparse
import gc
import importlib.util
import json
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "OPS-data-main9/00_transport_nyc/00_transport_nyc_256KiB.f64"
COMBINED_SOURCE = ROOT / "work/run_cached_fusion_ops_miner.py"
NOREUSE_SOURCE = Path(
    "/Users/zyj/Documents/Codex/2026-08-18/"
    "users-zyj-documents-codex-2026-08/OPS-ablation/OPS-NoReuse.py"
)
METADATA = ROOT / "OPS-data-main9/00_transport_nyc/metadata.json"

# The first setting is the existing baseline.  The remaining settings yield
# approximately 40, 60, 80, and 100 windows while retaining 90% overlap.
SETTINGS = [
    ("windows23", 10_000, 1_000, 5),
    ("windows40", 6_600, 660, 3),
    ("windows60", 4_700, 470, 3),
    ("windows80", 3_680, 368, 3),
    ("windows100", 3_000, 300, 3),
]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def run_once(cls, data, window: int, step: int, minsup: int):
    gc.collect()
    miner = cls(window, step, minsup)
    started = time.perf_counter()
    result = miner.find2(data)
    windows = 0
    patterns = 0
    while result is not None:
        windows += 1
        patterns += sum(map(len, result))
        result = miner.find2()
    return time.perf_counter() - started, windows, patterns


def run_fresh_process(name: str, window: int, step: int, minsup: int,
                      output: Path):
    if name == "Original-Combined":
        command = [
            sys.executable, str(ROOT / "work/run_cached_fusion_ops_miner.py"),
            "--dataset", str(DATASET), "--metadata", str(METADATA),
            "--window", str(window), "--step", str(step),
            "--minsup", str(minsup), "--output", str(output),
        ]
    else:
        command = [
            sys.executable, str(ROOT / "work/run_all_ops_algorithm.py"),
            "--algorithm", "OPS-NoReuse", "--dataset", str(DATASET),
            "--metadata", str(METADATA), "--window", str(window),
            "--step", str(step), "--minsup", str(minsup),
            "--output", str(output),
        ]
    subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    result = json.loads(output.read_text())
    return result["elapsed_seconds"], result["windows"], result["patterns_total"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=9)
    parser.add_argument("--fresh-processes", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs/NYC-reuse-window-count-sweep-overlap90.json",
    )
    args = parser.parse_args()

    classes = None
    if not args.fresh_processes:
        combined_module = load_module("combined_window_sweep", COMBINED_SOURCE)
        noreuse_module = load_module("noreuse_window_sweep", NOREUSE_SOURCE)
        classes = {
            "Original-Combined": combined_module.ScanAndFusionReuseMiner,
            "OPS-NoReuse": noreuse_module.OPSNoReuseMiner,
        }
    data = np.memmap(DATASET, dtype="<f8", mode="r")
    records = []

    with tempfile.TemporaryDirectory() as temporary:
        temporary_dir = Path(temporary)
        for label, window, step, minsup in SETTINGS:
            timings = {name: [] for name in ("Original-Combined", "OPS-NoReuse")}
            reference = None
            for repetition in range(args.repetitions):
                order = list(timings)
                if repetition % 2:
                    order.reverse()
                for name in order:
                    if args.fresh_processes:
                        elapsed, windows, patterns = run_fresh_process(
                            name, window, step, minsup,
                            temporary_dir / f"{label}-{name}-{repetition}.json",
                        )
                    else:
                        assert classes is not None
                        elapsed, windows, patterns = run_once(
                            classes[name], data, window, step, minsup
                        )
                    timings[name].append(elapsed)
                    observed = (windows, patterns)
                    if reference is None:
                        reference = observed
                    elif observed != reference:
                        raise RuntimeError(
                            f"result mismatch for {label} {name}: {observed} != {reference}"
                        )
            assert reference is not None
            reuse_median = statistics.median(timings["Original-Combined"])
            noreuse_median = statistics.median(timings["OPS-NoReuse"])
            records.append({
                "label": label,
                "data_length": len(data),
                "window": window,
                "step": step,
                "overlap": 1 - step / window,
                "minsup": minsup,
                "windows": reference[0],
                "patterns_total": reference[1],
                "patterns_mean_per_window": reference[1] / reference[0],
                "repetitions": args.repetitions,
                "fresh_processes": args.fresh_processes,
                "original_combined_seconds": timings["Original-Combined"],
                "noreuse_seconds": timings["OPS-NoReuse"],
                "original_combined_median_seconds": reuse_median,
                "noreuse_median_seconds": noreuse_median,
                "speedup": noreuse_median / reuse_median,
                "time_reduction_percent": (1 - reuse_median / noreuse_median) * 100,
            })
            print(json.dumps(records[-1], ensure_ascii=False), flush=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
