"""OPS-NoNumpy: OPS-Miner implemented with Python lists."""

import argparse
import time

class OPSNoNumpyMiner:
    """Use Python lists and dictionaries without NumPy."""

    def __init__(self, window_size, step_size, min_sup):
        self.window_size = int(window_size)
        self.step_size = int(step_size)
        self.min_sup = int(min_sup)
        self.data = []
        self.initial_runtime = 0.0
        self.update_runtimes = []

    def read_file(self, file_path):
        values = []
        with open(file_path, "r", encoding="utf-8") as stream:
            for line in stream:
                values.extend(
                    float(token)
                    for token in line.replace(",", " ").split()
                )
        return values

    def find2(self, values=None):
        """Process W1 without reuse, or Wk by reusing PIS2."""
        first_window = not hasattr(self, "length_two_ids")

        if first_window:
            start = time.perf_counter()
            self.data = list(values)
            self.length_two_ids = [0] * len(self.data)
            self.length_two_counts = [0, 0, 0]
            self.left = 0
            self.right = self.window_size - 1
            endpoints = range(1, self.right + 1)
        else:
            if self.right + self.step_size >= len(self.data):
                return None

            start = time.perf_counter()
            old_left = self.left
            old_right = self.right
            new_left = old_left + self.step_size
            new_right = old_right + self.step_size

            for endpoint in range(old_left + 1, new_left + 1):
                pattern_id = self.length_two_ids[endpoint]
                if pattern_id != 0:
                    self.length_two_counts[pattern_id] -= 1

            endpoints = range(old_right + 1, new_right + 1)

        # Length-2 scan shared by W1 and every reuse update.
        for endpoint in endpoints:
            left_value = self.data[endpoint - 1]
            right_value = self.data[endpoint]
            if left_value < right_value:
                pattern_id = 1
            elif left_value > right_value:
                pattern_id = 2
            else:
                pattern_id = 0
            self.length_two_ids[endpoint] = pattern_id
            if pattern_id != 0:
                self.length_two_counts[pattern_id] += 1

        if not first_window:
            self.left = new_left
            self.right = new_right

        miner_data = self.data[self.left:self.right + 1]
        position_ids = self.length_two_ids[self.left:self.right + 1]
        position_ids[0] = 0
        f2 = {}
        if self.length_two_counts[1] >= self.min_sup:
            f2[(1, 2)] = int(self.length_two_counts[1])
        if self.length_two_counts[2] >= self.min_sup:
            f2[(2, 1)] = int(self.length_two_counts[2])

        if len(f2) != 2:
            active_ids = list(position_ids)
            keep_1 = self.length_two_counts[1] >= self.min_sup
            keep_2 = self.length_two_counts[2] >= self.min_sup
            for index, pattern_id in enumerate(active_ids):
                if (pattern_id == 1 and not keep_1) or (
                    pattern_id == 2 and not keep_2
                ):
                    active_ids[index] = 0
        else:
            active_ids = position_ids

        old_data = self.data
        self.data = miner_data
        result = self._find_m(f2, active_ids, [None, (1, 2), (2, 1)])
        self.data = old_data

        if first_window:
            self.initial_runtime = time.perf_counter() - start
            self.update_runtimes = []
        else:
            self.update_runtimes.append(time.perf_counter() - start)
        return result

    def _find_m(self, f2, position_ids, id_to_pattern):
        current_patterns = f2
        current_ids = position_ids
        current_id_to_pattern = id_to_pattern
        levels = []
        while current_patterns:
            levels.append(dict(current_patterns))
            pattern_length = len(next(iter(current_patterns)))
            next_patterns, next_ids, next_id_to_pattern = (
                self._build_next_level(
                    pattern_length,
                    current_ids,
                    current_id_to_pattern,
                )
            )
            if not next_patterns:
                break
            current_patterns = next_patterns
            current_ids = next_ids
            current_id_to_pattern = next_id_to_pattern
        return levels

    def _build_next_level(self, pattern_length, current_ids, id_to_pattern):
        data_size = len(self.data)
        next_ids = [0] * data_size
        events = [None] * data_size
        event_counts = {}

        for endpoint in range(1, data_size):
            prefix_id = int(current_ids[endpoint - 1])
            suffix_id = int(current_ids[endpoint])
            if prefix_id == 0 or suffix_id == 0:
                continue

            start = endpoint - pattern_length
            tbegin = self.data[start]
            tend = self.data[endpoint]
            if tbegin < tend:
                relation = 1
            elif tbegin > tend:
                relation = 2
            else:
                relation = 0

            event = (prefix_id, suffix_id, relation)
            events[endpoint] = event
            event_counts[event] = event_counts.get(event, 0) + 1

        if not event_counts:
            return {}, next_ids, [None]

        event_to_candidate = {}
        frequent_patterns = {}
        for event, support in event_counts.items():
            if support < self.min_sup:
                continue
            prefix_id, suffix_id, relation = event
            candidate = self.frequent_pattern_fusion(
                id_to_pattern[prefix_id],
                id_to_pattern[suffix_id],
                relation,
            )
            event_to_candidate[event] = candidate
            if candidate is not None:
                frequent_patterns[candidate] = support

        next_id_to_pattern = [None]
        pattern_to_next_id = {}
        for pattern in frequent_patterns:
            pattern_to_next_id[pattern] = len(next_id_to_pattern)
            next_id_to_pattern.append(pattern)

        for endpoint, event in enumerate(events):
            if event is None:
                continue
            candidate = event_to_candidate.get(event)
            if candidate is not None:
                next_ids[endpoint] = pattern_to_next_id.get(candidate, 0)
        return frequent_patterns, next_ids, next_id_to_pattern

    def frequent_pattern_fusion(self, p, q, relation):
        """Generate only the super-pattern selected by a frequent event."""
        p1 = p[0]
        qm = q[-1]

        # Case A: p1 != qm.  Only one super-pattern is generated.
        if p1 < qm:
            r = [p1]
            r.extend(q)
            for i in range(1, len(r)):
                if r[i] >= r[0]:
                    r[i] += 1
            return tuple(r)

        # The second branch of Case A: p1 > qm.
        if p1 > qm:
            r = [p1 + 1]
            r.extend(q)
            for i in range(1, len(r)):
                if r[i] >= r[0]:
                    r[i] += 1
            return tuple(r)

        if relation == 0:
            return None

        middle = [value if value < p1 else value + 1 for value in p[1:]]
        if relation == 1:
            return tuple([p1] + middle + [p1 + 1])
        return tuple([p1 + 1] + middle + [p1])

    def run(self, file_path, max_updates=None):
        values = self.read_file(file_path)
        result = self.find2(values)
        updates = 0
        while max_updates is None or updates < max_updates:
            next_result = self.find2()
            if next_result is None:
                break
            result = next_result
            updates += 1
        return result, updates


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="OPS-NoNumpy: list-based PPC"
    )
    parser.add_argument("dataset", help="Path to a numeric time series")
    parser.add_argument("--window", type=int, required=True)
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--minsup", "--min-sup", type=int, required=True)
    parser.add_argument("--updates", type=int, default=None)
    args = parser.parse_args()

    algorithm = OPSNoNumpyMiner(
        args.window,
        args.step,
        args.minsup,
    )
    result, updates = algorithm.run(args.dataset, args.updates)
    print(f"Data length: {len(algorithm.data)}")
    print(f"Window size: {args.window}")
    print(f"Step size: {args.step}")
    print(f"Minimum support: {args.minsup}")
    print(f"Updates: {updates}")
    print(f"Level counts: {[len(level) for level in result]}")
    print(f"Total frequent patterns: {sum(map(len, result))}")
