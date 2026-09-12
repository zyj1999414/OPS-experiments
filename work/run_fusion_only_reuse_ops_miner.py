#!/usr/bin/env python3
"""OPS-NoReuse scanning with only cross-window pattern-fusion caching enabled."""

import argparse
import importlib.util
import json
import resource
import time
from pathlib import Path

import numpy as np

SOURCE = Path("/Users/zyj/Documents/Codex/2026-08-18/users-zyj-documents-codex-2026-08/OPS-ablation/OPS-NoReuse.py")
spec = importlib.util.spec_from_file_location("ops_noreuse_source", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FusionOnlyReuseMiner(module.OPSNoReuseMiner):
    def __init__(self, *args):
        super().__init__(*args)
        self.fusion_cache = {}
        self.fusion_cache_hits = 0
        self.fusion_cache_misses = 0

    def frequent_pattern_fusion(self, p, q, relation):
        key = (p, q, int(relation))
        try:
            result = self.fusion_cache[key]
            self.fusion_cache_hits += 1
            return result
        except KeyError:
            result = super().frequent_pattern_fusion(p, q, relation)
            self.fusion_cache[key] = result
            self.fusion_cache_misses += 1
            return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--window", type=int, required=True)
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--minsup", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    values = np.memmap(args.dataset, dtype="<f8", mode="r")
    metadata = json.loads(args.metadata.read_text())
    boundaries = metadata.get("boundaries") or [{"start": 0, "length": len(values)}]
    windows = patterns_total = hits = misses = entries = 0
    started = time.perf_counter()
    for boundary in boundaries:
        begin, length = int(boundary["start"]), int(boundary["length"])
        if length < args.window:
            continue
        miner = FusionOnlyReuseMiner(args.window, args.step, args.minsup)
        result = miner.find2(values[begin:begin + length])
        while result is not None:
            windows += 1
            patterns_total += sum(map(len, result))
            result = miner.find2()
        hits += miner.fusion_cache_hits
        misses += miner.fusion_cache_misses
        entries += len(miner.fusion_cache)
    elapsed = time.perf_counter() - started
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576
    summary = {
        "algorithm": "OPS-Miner-FusionOnlyReuse", "dataset": str(args.dataset),
        "window": args.window, "step": args.step, "minsup": args.minsup,
        "windows": windows, "patterns_total": patterns_total,
        "patterns_mean_per_window": patterns_total / windows if windows else None,
        "fusion_cache_hits": hits, "fusion_cache_misses": misses,
        "fusion_cache_entries": entries,
        "fusion_cache_hit_rate": hits / (hits + misses) if hits + misses else None,
        "elapsed_seconds": elapsed, "peak_rss_mib": peak,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
