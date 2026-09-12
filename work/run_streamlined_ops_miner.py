#!/usr/bin/env python3
"""Run the necessary-operations-only PIS2 reuse implementation."""

import argparse
import importlib.util
import json
import resource
import time
from pathlib import Path

import numpy as np

SOURCE = Path("/Users/zyj/Documents/Codex/2026-08-18/users-zyj-documents-codex-2026-08/OPS-ablation/OPS-Miner.py")
spec = importlib.util.spec_from_file_location("ops_streamlined_source", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class StreamlinedReuseMiner(module.L2IncrementalPPCNewsup):
    def find2(self, values=None):
        first = not hasattr(self, "length_two_ids") or self.length_two_ids.size == 0
        if first:
            return super().find2(values)
        if self.right + self.step_size >= self.data.size:
            return None

        old_left, old_right = self.left, self.right
        new_left = old_left + self.step_size
        new_right = old_right + self.step_size

        leaving_ids = self.length_two_ids[old_left + 1:new_left + 1]
        removed = np.bincount(leaving_ids, minlength=3)
        self.length_two_counts[1:3] -= removed[1:3]

        start, stop = old_right + 1, new_right + 1
        left_values = self.data[start - 1:stop - 1]
        right_values = self.data[start:stop]
        ids = np.where(left_values < right_values, 1,
                       np.where(left_values > right_values, 2, 0)).astype(np.int32, copy=False)
        self.length_two_ids[start:stop] = ids
        added = np.bincount(ids, minlength=3)
        self.length_two_counts[1:3] += added[1:3]

        self.left, self.right = new_left, new_right
        miner_data = self.data[self.left:self.right + 1]
        position_ids = self.length_two_ids[self.left:self.right + 1]
        boundary_id = int(position_ids[0])
        position_ids[0] = 0

        f2 = {}
        if self.length_two_counts[1] >= self.min_sup:
            f2[(1, 2)] = int(self.length_two_counts[1])
        if self.length_two_counts[2] >= self.min_sup:
            f2[(2, 1)] = int(self.length_two_counts[2])
        if len(f2) != 2:
            active_ids = position_ids.copy()
            keep = np.zeros(3, dtype=bool)
            keep[1] = self.length_two_counts[1] >= self.min_sup
            keep[2] = self.length_two_counts[2] >= self.min_sup
            active_ids[~keep[active_ids]] = 0
        else:
            active_ids = position_ids

        old_data = self.data
        self.data = miner_data
        result = self._find_m(f2, active_ids, [None, (1, 2), (2, 1)])
        self.data = old_data
        position_ids[0] = boundary_id
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
    windows = patterns_total = 0
    started = time.perf_counter()
    for boundary in boundaries:
        begin, length = int(boundary["start"]), int(boundary["length"])
        if length < a.window:
            continue
        miner = StreamlinedReuseMiner(a.window, a.step, a.minsup)
        result = miner.find2(values[begin:begin + length])
        while result is not None:
            windows += 1
            patterns_total += sum(map(len, result))
            result = miner.find2()
    elapsed = time.perf_counter() - started
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    summary = {
        "algorithm": "OPS-Miner-StreamlinedReuse", "dataset": str(a.dataset),
        "window": a.window, "step": a.step, "minsup": a.minsup,
        "windows": windows, "patterns_total": patterns_total,
        "patterns_mean_per_window": patterns_total / windows if windows else None,
        "elapsed_seconds": elapsed, "peak_rss_mib": peak / 1048576,
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
