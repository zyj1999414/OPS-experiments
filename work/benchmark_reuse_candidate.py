#!/usr/bin/env python3
"""Benchmark OPS-Miner (combined reuse) and OPS-NoReuse in fresh processes."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def command(name: str, args, metadata: Path, output: Path) -> list[str]:
    common = [
        "--dataset", str(args.dataset), "--metadata", str(metadata),
        "--window", str(args.window), "--step", str(args.step),
        "--minsup", str(args.minsup), "--output", str(output),
    ]
    if name == "OPS-Miner":
        return [sys.executable, str(ROOT / "work/run_cached_fusion_ops_miner.py"), *common]
    return [sys.executable, str(ROOT / "work/run_all_ops_algorithm.py"),
            "--algorithm", "OPS-NoReuse", *common]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--prefix", type=int)
    parser.add_argument("--window", type=int, required=True)
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--minsup", type=int, required=True)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.dataset = args.dataset.resolve()

    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        if args.prefix is not None:
            metadata = tmp / "metadata.json"
            metadata.write_text(json.dumps({"boundaries": [{"start": 0, "length": args.prefix}]}))
        elif args.metadata is not None:
            metadata = args.metadata.resolve()
        else:
            metadata = tmp / "metadata.json"
            points = args.dataset.stat().st_size // 8
            metadata.write_text(json.dumps({"boundaries": [{"start": 0, "length": points}]}))

        raw = {"OPS-Miner": [], "OPS-NoReuse": []}
        for repetition in range(args.repetitions):
            for name in ("OPS-Miner", "OPS-NoReuse"):
                output = tmp / f"{repetition}-{name}.json"
                subprocess.run(
                    command(name, args, metadata, output), cwd=ROOT, check=True,
                    capture_output=True, text=True, timeout=args.timeout,
                )
                raw[name].append(json.loads(output.read_text()))
                print(f"{repetition + 1}/{args.repetitions} {name}: "
                      f"{raw[name][-1]['elapsed_seconds']:.6f}s", flush=True)

    medians = {
        name: statistics.median(x["elapsed_seconds"] for x in results)
        for name, results in raw.items()
    }
    reference = raw["OPS-Miner"][0]
    result = {
        "dataset": str(args.dataset), "window": args.window, "step": args.step,
        "minsup": args.minsup, "prefix": args.prefix,
        "repetitions": args.repetitions, "windows": reference["windows"],
        "patterns_total": reference["patterns_total"],
        "patterns_mean": reference["patterns_mean_per_window"],
        "median_seconds": medians,
        "speedup": medians["OPS-NoReuse"] / medians["OPS-Miner"],
        "time_reduction_percent": (1 - medians["OPS-Miner"] / medians["OPS-NoReuse"]) * 100,
        "raw": raw,
    }
    no_ref = raw["OPS-NoReuse"][0]
    if (reference["patterns_total"], reference["windows"]) != (no_ref["patterns_total"], no_ref["windows"]):
        raise RuntimeError("Pattern totals or window counts differ")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "raw"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
