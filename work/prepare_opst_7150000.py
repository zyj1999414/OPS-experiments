from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "OPS-data/01_finance_binance/01_finance_binance_64MiB.f64"
TARGET = ROOT / "work/OPST-source/data/binance_7150000_dense_rank.txt"
LENGTH = 7_150_000

values = np.memmap(SOURCE, dtype="<f8", mode="r", shape=(LENGTH,))
# OPST accepts integer input. Dense ranks preserve <, >, and = relations.
ranks = np.unique(values, return_inverse=True)[1].astype(np.int32, copy=False) + 1
TARGET.parent.mkdir(parents=True, exist_ok=True)
np.savetxt(TARGET, ranks, fmt="%d")

with TARGET.open("rb") as stream:
    lines = sum(chunk.count(b"\n") for chunk in iter(lambda: stream.read(8 << 20), b""))
assert lines == LENGTH
print(TARGET)
print("points", lines)
print("unique_ranks", int(ranks.max()))
print("bytes", TARGET.stat().st_size)
