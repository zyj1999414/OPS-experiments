#!/usr/bin/env python3
"""Low-overhead PIS2 + fusion reuse with optimized higher-order rebuilds."""

import argparse
import importlib.util
import json
import resource
import time
from pathlib import Path

import numpy as np

STREAMLINED = Path(__file__).with_name("run_streamlined_ops_miner.py")
spec = importlib.util.spec_from_file_location("streamlined_for_optimized", STREAMLINED)
streamlined = importlib.util.module_from_spec(spec)
spec.loader.exec_module(streamlined)


class OptimizedCombinedMiner(streamlined.StreamlinedReuseMiner):
    def __init__(self, *args):
        super().__init__(*args)
        self.fusion_cache = {}
        self.fusion_cache_hits = 0
        self.fusion_cache_misses = 0
        self._level_buffers = {}

    def frequent_pattern_fusion(self, p, q, relation):
        key = (p, q, int(relation))
        try:
            candidate = self.fusion_cache[key]
            self.fusion_cache_hits += 1
            return candidate
        except KeyError:
            candidate = super().frequent_pattern_fusion(p, q, relation)
            self.fusion_cache[key] = candidate
            self.fusion_cache_misses += 1
            return candidate

    def _next_buffer(self, child_length, size):
        buffer = self._level_buffers.get(child_length)
        if buffer is None or buffer.size != size:
            buffer = np.zeros(size, dtype=np.int32)
            self._level_buffers[child_length] = buffer
        else:
            buffer.fill(0)
        return buffer

    def _build_next_level(self, pattern_length, current_ids, id_to_pattern):
        data_size = self.data.size
        child_length = pattern_length + 1
        next_ids = self._next_buffer(child_length, data_size)
        prefix_ids = current_ids[:-1]
        suffix_ids = current_ids[1:]
        aligned_indices = np.flatnonzero((prefix_ids != 0) & (suffix_ids != 0))
        if aligned_indices.size == 0:
            return {}, next_ids, [None]
        endpoints = aligned_indices + 1
        starts = endpoints - pattern_length
        tbegin = self.data[starts]
        tend = self.data[endpoints]
        relations = np.where(
            tbegin < tend, 1, np.where(tbegin > tend, 2, 0)
        ).astype(np.int32, copy=False)
        id_base = len(id_to_pattern)
        if id_base <= 26_000:
            active_prefix_ids = prefix_ids[aligned_indices]
            active_suffix_ids = suffix_ids[aligned_indices]
        else:
            active_prefix_ids = prefix_ids[aligned_indices].astype(np.int64, copy=False)
            active_suffix_ids = suffix_ids[aligned_indices].astype(np.int64, copy=False)
            relations = relations.astype(np.int64, copy=False)
        event_keys = (active_prefix_ids * id_base + active_suffix_ids) * 3 + relations

        max_event_key = int(event_keys.max())
        dense_key_limit = min(4_000_000, int(event_keys.size) * 16)
        use_bincount = max_event_key <= dense_key_limit
        if use_bincount:
            counts_by_key = np.bincount(event_keys)
            unique_keys = np.flatnonzero(counts_by_key)
            counts = counts_by_key[unique_keys]
            inverse = None
        else:
            unique_keys, inverse, counts = np.unique(
                event_keys, return_inverse=True, return_counts=True
            )

        frequent_group_indices = np.flatnonzero(counts >= self.min_sup)
        frequent_patterns = {}
        next_id_to_pattern = [None]
        pattern_to_next_id = {}
        group_to_next_id = np.zeros(unique_keys.size, dtype=np.int32)
        for group_index in frequent_group_indices.tolist():
            event_key = int(unique_keys[group_index])
            relation = event_key % 3
            pair_key = event_key // 3
            prefix_id = pair_key // id_base
            suffix_id = pair_key % id_base
            candidate = self.frequent_pattern_fusion(
                id_to_pattern[prefix_id], id_to_pattern[suffix_id], relation
            )
            if candidate is None:
                continue
            frequent_patterns[candidate] = int(counts[group_index])
            next_id = pattern_to_next_id.get(candidate)
            if next_id is None:
                next_id = len(next_id_to_pattern)
                pattern_to_next_id[candidate] = next_id
                next_id_to_pattern.append(candidate)
            group_to_next_id[group_index] = next_id

        if use_bincount:
            key_to_next_id = np.zeros(max_event_key + 1, dtype=np.int32)
            key_to_next_id[unique_keys] = group_to_next_id
            next_ids[endpoints] = key_to_next_id[event_keys]
        else:
            next_ids[endpoints] = group_to_next_id[inverse]
        return frequent_patterns, next_ids, next_id_to_pattern


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
    windows = patterns_total = hits = misses = 0
    started = time.perf_counter()
    for boundary in boundaries:
        begin, length = int(boundary["start"]), int(boundary["length"])
        if length < a.window:
            continue
        miner = OptimizedCombinedMiner(a.window, a.step, a.minsup)
        result = miner.find2(values[begin:begin + length])
        while result is not None:
            windows += 1
            patterns_total += sum(map(len, result))
            result = miner.find2()
        hits += miner.fusion_cache_hits
        misses += miner.fusion_cache_misses
    elapsed = time.perf_counter() - started
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576
    summary = {
        "algorithm": "OPS-OptimizedCombinedReuse", "dataset": str(a.dataset),
        "window": a.window, "step": a.step, "minsup": a.minsup,
        "windows": windows, "patterns_total": patterns_total,
        "patterns_mean_per_window": patterns_total / windows if windows else None,
        "fusion_cache_hits": hits, "fusion_cache_misses": misses,
        "elapsed_seconds": elapsed, "peak_rss_mib": peak,
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
