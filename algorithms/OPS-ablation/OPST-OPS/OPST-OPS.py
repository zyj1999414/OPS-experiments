"""OPST with OPS-Miner sliding windows and no reuse."""

import argparse
import time

import numpy as np

from opst import OPST


def sort_pattern(values):
    order = np.asarray(values).argsort().argsort() + 1
    return tuple(int(value) for value in order)


class OPSTOPS:
    def __init__(self, window_size, step_size, min_sup, range_threshold=512):
        self.window_size = int(window_size)
        self.step_size = int(step_size)
        self.min_sup = int(min_sup)
        self.range_threshold = int(range_threshold)
        self.window_runtimes = []

    def read_file(self, file_path):
        values = []
        with open(file_path, "r", encoding="utf-8") as stream:
            for line in stream:
                values.extend(
                    float(token)
                    for token in line.replace(",", " ").split()
                )
        return values

    def mine_window(self, window):
        construction_start = time.perf_counter()
        tree = OPST(list(window), self.range_threshold)
        construction_time = time.perf_counter() - construction_start

        mining_start = time.perf_counter()
        tree.MaxTauDFS(self.min_sup)
        maximal_nodes = tree.MaxFindNodes()
        mining_time = time.perf_counter() - mining_start

        patterns = {}
        for node, support in maximal_nodes.items():
            start = node.start
            end = start + node.depth
            if node.depth > 0 and start >= 0 and end <= len(window):
                patterns[sort_pattern(window[start:end])] = support

        return {
            "patterns": patterns,
            "maximal_count": len(patterns),
            "construction_time": construction_time,
            "mining_time": mining_time,
            "runtime": construction_time + mining_time,
            "wavelet_time": tree.waveletTime,
        }

    def run(self, file_path, max_updates=None):
        data = self.read_file(file_path)
        if len(data) < self.window_size:
            raise ValueError("data shorter than window")

        results = []
        left = 0
        while left + self.window_size <= len(data):
            window = data[left:left + self.window_size]
            results.append(self.mine_window(window))
            if max_updates is not None and len(results) > max_updates:
                break
            left += self.step_size

        self.window_runtimes = [result["runtime"] for result in results]
        return data, results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="OPST with OPS-Miner sliding windows and no reuse"
    )
    parser.add_argument("dataset")
    parser.add_argument("--window", type=int, required=True)
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--minsup", "--min-sup", type=int, required=True)
    parser.add_argument("--range-threshold", type=int, default=512)
    parser.add_argument("--updates", type=int, default=None)
    args = parser.parse_args()

    algorithm = OPSTOPS(
        args.window,
        args.step,
        args.minsup,
        args.range_threshold,
    )
    data, results = algorithm.run(args.dataset, args.updates)
    last = results[-1]
    print(f"Data length: {len(data)}")
    print(f"Window size: {args.window}")
    print(f"Step size: {args.step}")
    print(f"Minimum support: {args.minsup}")
    print(f"Updates: {len(results) - 1}")
    print(f"Maximal OPPs: {last['maximal_count']}")
    print(f"Total runtime: {sum(algorithm.window_runtimes):.6f} s")
