#!/usr/bin/env python3
"""OPS-Miner with both PIS2 scan reuse and cross-window fusion reuse."""

import argparse
import importlib.util
import json
import resource
import time
from pathlib import Path

import numpy as np

STREAMLINED = Path(__file__).with_name("run_streamlined_ops_miner.py")
spec = importlib.util.spec_from_file_location("streamlined_ops", STREAMLINED)
streamlined = importlib.util.module_from_spec(spec)
spec.loader.exec_module(streamlined)


class ScanAndFusionReuseMiner(streamlined.StreamlinedReuseMiner):
    def __init__(self, *args):
        super().__init__(*args)
        self.fusion_cache = {}
        self.fusion_cache_hits = 0
        self.fusion_cache_misses = 0

    def frequent_pattern_fusion(self, p, q, relation):
        # Numeric IDs are local to a window/level and can be reassigned.
        # Pattern tuples plus C are stable and therefore safe across windows.
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
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--metadata", type=Path, required=True)
    p.add_argument("--window", type=int, required=True)
    p.add_argument("--step", type=int, required=True)
    p.add_argument("--minsup", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    values = np.memmap(a.dataset, dtype="<f8", mode="r")
    metadata = json.loads(a.metadata.read_text())
    boundaries = metadata.get("boundaries") or [{"start": 0, "length": len(values)}]
    windows = patterns_total = hits = misses = cache_entries = 0
    started = time.perf_counter()
    for boundary in boundaries:
        begin, length = int(boundary["start"]), int(boundary["length"])
        if length < a.window:
            continue
        miner = ScanAndFusionReuseMiner(a.window, a.step, a.minsup)
        result = miner.find2(values[begin:begin + length])
        while result is not None:
            windows += 1
            patterns_total += sum(map(len, result))
            result = miner.find2()
        hits += miner.fusion_cache_hits
        misses += miner.fusion_cache_misses
        cache_entries += len(miner.fusion_cache)
    elapsed = time.perf_counter() - started
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    summary = {
        "algorithm": "OPS-Miner",
        "fusion_cache_key": "(prefix_pattern, suffix_pattern, C)",
        "dataset": str(a.dataset), "window": a.window, "step": a.step,
        "minsup": a.minsup, "windows": windows,
        "patterns_total": patterns_total,
        "patterns_mean_per_window": patterns_total / windows if windows else None,
        "fusion_cache_hits": hits, "fusion_cache_misses": misses,
        "fusion_cache_entries": cache_entries,
        "fusion_cache_hit_rate": hits / (hits + misses) if hits + misses else None,
        "elapsed_seconds": elapsed, "peak_rss_mib": peak / 1048576,
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
