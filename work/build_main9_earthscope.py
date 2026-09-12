#!/usr/bin/env python3
"""Download and build the 1 GiB EarthScope seismic OPS input."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from obspy import read


ROOT = Path(__file__).resolve().parents[1]
DOWNLOAD = ROOT / "work/main9-downloads/earthscope"
OUTPUT_DIR = ROOT / "OPS-data-main9/08_seismic_earthscope"
OUTPUT = OUTPUT_DIR / "08_seismic_earthscope_1GiB.f64"
TARGET_SAMPLES = 134_217_728
START = date(2024, 1, 1)
DAYS = 16


def download_day(day: date) -> Path:
    next_day = day + timedelta(days=1)
    path = DOWNLOAD / f"IU.ANMO.00.HHZ.{day.isoformat()}.mseed"
    if path.exists() and path.stat().st_size:
        return path
    url = (
        "https://service.earthscope.org/fdsnws/dataselect/1/query"
        f"?net=IU&sta=ANMO&loc=00&cha=HHZ&starttime={day.isoformat()}T00:00:00"
        f"&endtime={next_day.isoformat()}T00:00:00&format=miniseed&nodata=404"
    )
    temp = path.with_suffix(path.suffix + ".part")
    subprocess.run(
        ["curl", "-fL", "--retry", "5", "--retry-all-errors",
         "--connect-timeout", "20", "--max-time", "600", "-o", str(temp), url],
        check=True,
    )
    temp.replace(path)
    return path


def main() -> None:
    DOWNLOAD.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = [download_day(START + timedelta(days=i)) for i in range(DAYS)]

    written = 0
    starts = []
    ends = []
    with OUTPUT.open("wb") as target:
        for path in paths:
            stream = read(str(path))
            stream.merge(method=-1)
            if len(stream) != 1:
                raise RuntimeError(f"{path}: expected one continuous trace, got {len(stream)}")
            trace = stream[0]
            if trace.stats.sampling_rate != 100.0:
                raise RuntimeError(f"{path}: sample rate is {trace.stats.sampling_rate}, not 100 Hz")
            data = trace.data
            if np.ma.isMaskedArray(data) and np.any(data.mask):
                raise RuntimeError(f"{path}: contains {int(np.sum(data.mask))} missing samples")
            take = min(len(data), TARGET_SAMPLES - written)
            np.asarray(data[:take], dtype="<f8").tofile(target)
            written += take
            starts.append(str(trace.stats.starttime))
            ends.append(str(trace.stats.endtime))
            print(f"{path.name}: {len(data):,} samples; total written {written:,}")
            if written == TARGET_SAMPLES:
                break

    if written != TARGET_SAMPLES:
        raise RuntimeError(f"only wrote {written:,} of {TARGET_SAMPLES:,} samples")

    metadata = {
        "dataset": "EarthScope IU.ANMO.00.HHZ continuous seismic waveform",
        "domain": "seismology",
        "source": "NSF EarthScope FDSN dataselect",
        "source_url": "https://service.earthscope.org/fdsnws/dataselect/1/",
        "network": "IU",
        "station": "ANMO",
        "location": "00",
        "channel": "HHZ",
        "variable": "vertical ground-velocity sensor counts",
        "sample_rate_hz": 100.0,
        "samples": TARGET_SAMPLES,
        "boundaries": [{"start": 0, "length": TARGET_SAMPLES}],
        "dtype": "float64 little-endian",
        "bytes": OUTPUT.stat().st_size,
        "duration_seconds": TARGET_SAMPLES / 100.0,
        "window": 8_640_000,
        "step": 864_000,
        "minsup": 86_400,
        "window_meaning": "24 hours of continuous vertical seismic waveform",
        "downloaded_files": [p.name for p in paths],
        "trace_start_times": starts,
        "trace_end_times": ends,
        "missing_samples": 0,
        "notes": "Raw integer miniSEED counts converted to float64 without interpolation or synthetic padding.",
    }
    (OUTPUT_DIR / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
