#!/usr/bin/env python3
"""Extract 256 MiB of continuous calibrated BLOND-250 phase-1 current."""

import json
from pathlib import Path

import h5py
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "work/main9-downloads/blond"
OUTPUT_DIR = ROOT / "OPS-data-main9/06_power_blond250"
TARGET = 33_554_432


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / "06_power_blond250_256MiB.f64"
    written = 0
    sources = []
    with output.open("wb") as destination:
        for source in sorted(SOURCE_DIR.glob("*.hdf5")):
            with h5py.File(source, "r") as hdf:
                dataset = hdf["current1"]
                take = min(len(dataset), TARGET - written)
                factor = float(dataset.attrs["calibration_factor"])
                block = 1_000_000
                for start in range(0, take, block):
                    stop = min(start + block, take)
                    values = np.asarray(dataset[start:stop], dtype=np.float64) * factor
                    np.asarray(values, dtype="<f8").tofile(destination)
                sources.append(
                    {
                        "file": source.name,
                        "sequence": int(hdf.attrs["sequence"]),
                        "first_trigger_id": int(hdf.attrs["first_trigger_id"]),
                        "last_trigger_id": int(hdf.attrs["last_trigger_id"]),
                        "values_used": take,
                    }
                )
                written += take
            if written == TARGET:
                break
    if written != TARGET:
        raise RuntimeError(f"wrote {written}, need {TARGET}")
    metadata = {
        "source": "rsync://m1375836@dataserv.ub.tum.de/m1375836/BLOND/BLOND-250/",
        "domain": "electrical power",
        "variable": "calibrated aggregate phase-1 current",
        "sample_rate_hz": 250000,
        "values": written,
        "bytes": output.stat().st_size,
        "format": "headerless little-endian float64",
        "sources": sources,
    }
    (OUTPUT_DIR / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
