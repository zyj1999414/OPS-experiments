#!/usr/bin/env python3
"""Extract one complete Sleep-EDF Fpz-Cz recording (approximately 64 MiB)."""

import json
from pathlib import Path

import numpy as np
import pyedflib


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "work/ops-data-downloads/sleep-edfx/sleep-cassette/SC4002E0-PSG.edf"
OUTPUT_DIR = ROOT / "OPS-data-main9/04_biomedical_sleep_edf"


def main() -> None:
    reader = pyedflib.EdfReader(str(SOURCE))
    try:
        labels = [label.strip() for label in reader.getSignalLabels()]
        channel = next(i for i, label in enumerate(labels) if "FPZ-CZ" in label.upper())
        values = np.asarray(reader.readSignal(channel), dtype="<f8")
        sample_rate = float(reader.getSampleFrequency(channel))
    finally:
        reader.close()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / "04_biomedical_sleep_edf_approx64MiB.f64"
    values.tofile(output)
    metadata = {
        "source": "https://physionet.org/files/sleep-edfx/1.0.0/sleep-cassette/SC4002E0-PSG.edf",
        "source_file": str(SOURCE),
        "domain": "biomedical EEG",
        "variable": "EEG Fpz-Cz",
        "sample_rate_hz": sample_rate,
        "values": len(values),
        "bytes": output.stat().st_size,
        "format": "headerless little-endian float64",
        "boundaries": [{"record": "SC4002E0", "start": 0, "length": len(values)}],
    }
    (OUTPUT_DIR / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
