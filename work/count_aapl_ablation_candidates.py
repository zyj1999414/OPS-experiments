#!/usr/bin/env python3
"""Count generated candidates for one full AAPL window across OPS ablations."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
BASE = Path("/Users/zyj/Documents/Codex/2026-08-18/users-zyj-documents-codex-2026-08/OPS-ablation")
AAPL = Path("/Users/zyj/Downloads/AAPL.txt")
WINDOW = 13_620
STEP = 13_620
MINSUP = 12

SPECS = {
    "OPS-Miner": (ROOT / "work/run_cached_fusion_ops_miner.py", "ScanAndFusionReuseMiner", "fusion"),
    "-1OPS-Miner": ("OPS-Miner.py", "L2IncrementalPPCNewsup", "fusion"),
    "OPS-NoReuse": ("OPS-NoReuse.py", "OPSNoReuseMiner", "fusion"),
    "OPS-NoNumpy": ("OPS-NoNumpy.py", "OPSNoNumpyMiner", "fusion"),
    "OPS-PF": ("OPS-PF.py", "OPSPFMiner", "fusion"),
    "OPS-Enum": ("OPS-Enum.py", "OPSEnumMiner", "enum"),
    "OPS-ISC": ("OPS-ISC.py", "OPSISC", "stateful"),
    "OPS-SPF": ("OPS-SPF.py", "OPSSPF", "stateful"),
    "EFO-OPS": ("EFO-OPS.py", "EFOOPS", "window"),
    "OPF-OPS": ("OPF-OPS.py", "OPFOPS", "window"),
    "SOPP-OPS": ("SOPP-OPS.py", "SOPPOPS", "window"),
    "OPST-OPS": ("OPST-OPS/OPST-OPS.py", "OPSTOPS", "opst"),
}


def load_module(name: str, relative):
    if name == "OPF-OPS" and "zmq.utils" not in sys.modules:
        zmq = types.ModuleType("zmq")
        utils = types.ModuleType("zmq.utils")
        utils.monitor = None
        zmq.utils = utils
        sys.modules["zmq"] = zmq
        sys.modules["zmq.utils"] = utils
    if name == "SOPP-OPS" and "memory_profiler" not in sys.modules:
        mp = types.ModuleType("memory_profiler")
        mp.memory_usage = lambda *args, **kwargs: []
        sys.modules["memory_profiler"] = mp
    if name == "OPST-OPS":
        sys.path.insert(0, str(BASE / "OPST-OPS"))
    source = relative if isinstance(relative, Path) else BASE / relative
    spec = importlib.util.spec_from_file_location(
        "candidate_" + name.replace("-", "_"), source
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def count_fusion(instance, values):
    count = 2
    original = instance.frequent_pattern_fusion

    def wrapped(*args, **kwargs):
        nonlocal count
        candidate = original(*args, **kwargs)
        if candidate is not None:
            count += 1
        return candidate

    instance.frequent_pattern_fusion = wrapped
    levels = instance.find2(values)
    return count, sum(map(len, levels))


def count_enum(instance, values):
    count = 2
    original = instance._build_fusion_table

    def wrapped(*args, **kwargs):
        nonlocal count
        transitions = original(*args, **kwargs)
        # Multiple relation keys may point to the same enumerated extension.
        # Count each materialized candidate pattern once per level.
        count += len({candidate for candidate in transitions.values() if candidate is not None})
        return transitions

    instance._build_fusion_table = wrapped
    levels = instance.find2(values)
    return count, sum(map(len, levels))


def main():
    values = np.loadtxt(AAPL, dtype=np.float64)
    if len(values) != WINDOW:
        raise RuntimeError(f"expected {WINDOW} values, got {len(values)}")
    rows = []
    for name, (relative, class_name, kind) in SPECS.items():
        module = load_module(name, relative)
        cls = getattr(module, class_name)
        if kind in {"fusion", "enum"}:
            data = values.tolist() if name == "OPS-NoNumpy" else values
            instance = cls(WINDOW, STEP, MINSUP)
            candidates, frequent = (
                count_enum(instance, data) if kind == "enum" else count_fusion(instance, data)
            )
            metric = "generated candidate patterns (including length-2)"
        elif kind == "stateful":
            module.read_file = lambda _path, segment=values: segment
            instance = cls("AAPL", WINDOW, STEP, MINSUP)
            result = instance.solve_window(True)
            candidates = int(result["candidate_patterns"])
            frequent = int(result["frequent_patterns"])
            metric = "native candidate_patterns counter"
        elif kind == "window":
            instance = cls(WINDOW, STEP, MINSUP)
            result = instance.mine_window(values)
            candidates = int(result["candidates"])
            frequent = int(result["frequent"])
            metric = "native candidates counter"
        else:
            ranked = (np.unique(values, return_inverse=True)[1] + 1).tolist()
            instance = cls(WINDOW, STEP, MINSUP)
            result = instance.mine_window(ranked)
            candidates = None
            frequent = int(result["maximal_count"])
            metric = "not applicable: suffix-tree maximal mining has no candidate set"
        row = {
            "algorithm": name,
            "candidate_patterns": candidates,
            "reported_patterns": frequent,
            "pattern_semantics": "maximal frequent patterns" if kind == "opst" else "frequent patterns",
            "counter_semantics": metric,
        }
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    output = ROOT / "outputs/aapl-minsup12-one-window-ablation-candidates.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "dataset": str(AAPL), "length": len(values), "window": WINDOW,
        "step": STEP, "minsup": MINSUP, "windows": 1, "results": rows,
    }, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
