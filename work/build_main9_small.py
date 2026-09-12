#!/usr/bin/env python3
"""Build the two smallest OPS main-experiment inputs from public real data."""

import json
from pathlib import Path

import numpy as np
from scipy.io import loadmat


ROOT = Path(__file__).resolve().parents[1]


def write_dataset(directory: Path, filename: str, values: np.ndarray, metadata: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / filename
    np.asarray(values, dtype="<f8").tofile(output)
    metadata = dict(metadata)
    metadata.update(
        values=int(len(values)),
        bytes=int(output.stat().st_size),
        format="headerless little-endian float64",
    )
    (directory / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )


def main() -> None:
    # The selected MAWI server trace was impractically slow to download. Use
    # the already downloaded public NYC TLC trip stream for this small event-
    # stream tier; this is a source-preserving prefix, not duplicated data.
    nyc_source = ROOT / "OPS-data/05_transport_nyc_tlc/05_transport_nyc_tlc_640MiB.f64"
    nyc = np.memmap(nyc_source, dtype="<f8", mode="r")[:32_768]
    write_dataset(
        ROOT / "OPS-data-main9/00_transport_nyc",
        "00_transport_nyc_256KiB.f64",
        nyc,
        {
            "source": "https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page",
            "domain": "urban transportation event stream",
            "variable": "trip duration seconds",
            "source_file": str(nyc_source),
            "selection": "first 32768 source observations",
        },
    )

    cwru_source = ROOT / "work/main9-downloads/cwru/97.mat"
    cwru = loadmat(cwru_source)["X097_DE_time"].reshape(-1)[:100_000]
    write_dataset(
        ROOT / "OPS-data-main9/01_industrial_cwru",
        "01_industrial_cwru_800KB.f64",
        cwru,
        {
            "source": "https://engineering.case.edu/sites/default/files/97.mat",
            "domain": "industrial machinery vibration",
            "variable": "drive-end accelerometer vibration",
            "source_file": str(cwru_source),
            "selection": "first 100000 observations of X097_DE_time",
        },
    )

    # NOAA USCRN publishes one 5-minute observation per row. Column 9 is air
    # temperature. Missing sentinels are omitted (178 of 526176 rows); no
    # values are interpolated or synthesized.
    noaa_files = sorted((ROOT / "work/main9-downloads/noaa-uscrn").glob("*.txt"))
    chunks = []
    missing = 0
    for source in noaa_files:
        values = np.loadtxt(source, usecols=(8,), dtype=np.float64)
        valid = values > -9990
        missing += int((~valid).sum())
        chunks.append(values[valid])
    noaa = np.concatenate(chunks)[:524_288]
    write_dataset(
        ROOT / "OPS-data-main9/02_weather_noaa_uscrn",
        "02_weather_noaa_uscrn_4MiB.f64",
        noaa,
        {
            "source": "https://www.ncei.noaa.gov/pub/data/uscrn/products/subhourly01/",
            "domain": "weather",
            "variable": "5-minute air temperature in degrees C",
            "station": "CO Boulder 14 W",
            "years": [2020, 2021, 2022, 2023, 2024],
            "missing_source_rows_omitted": missing,
            "selection": "first 524288 finite published observations; no interpolation",
        },
    )


if __name__ == "__main__":
    main()
