#!/usr/bin/env python3
"""Extract 512 MiB of consecutive BTCUSDT spot trade prices."""

import json
import zipfile
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    ROOT / "work/ops-data-downloads/BTCUSDT-trades-2024-01.zip",
    ROOT / "work/main9-downloads/binance/BTCUSDT-trades-2024-02.zip",
]
OUTPUT_DIR = ROOT / "OPS-data-main9/07_finance_binance"
TARGET = 67_108_864


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / "07_finance_binance_512MiB.f64"
    written = 0
    used = []
    buffer = []
    with output.open("wb") as destination:
        for source in SOURCES:
            source_count = 0
            with zipfile.ZipFile(source) as archive:
                member = archive.namelist()[0]
                with archive.open(member) as rows:
                    for raw in rows:
                        # Official spot-trades CSV: trade id, price, ...
                        buffer.append(float(raw.split(b",", 2)[1]))
                        source_count += 1
                        if len(buffer) == 1_000_000:
                            take = min(len(buffer), TARGET - written)
                            np.asarray(buffer[:take], dtype="<f8").tofile(destination)
                            written += take
                            buffer.clear()
                            if written == TARGET:
                                break
            used.append({"file": source.name, "rows_used": source_count})
            if written == TARGET:
                break
        if written < TARGET and buffer:
            take = min(len(buffer), TARGET - written)
            np.asarray(buffer[:take], dtype="<f8").tofile(destination)
            written += take
    if written != TARGET:
        raise RuntimeError(f"wrote {written}, need {TARGET}")
    metadata = {
        "source": "https://data.binance.vision/data/spot/monthly/trades/BTCUSDT/",
        "domain": "finance event stream",
        "variable": "BTCUSDT spot trade price",
        "values": written,
        "bytes": output.stat().st_size,
        "format": "headerless little-endian float64",
        "sources": used,
    }
    (OUTPUT_DIR / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
