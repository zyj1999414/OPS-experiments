#!/usr/bin/env python3
"""Build a 16 MiB Kepler short-cadence corpus while preserving star boundaries."""

import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
from astropy.io import fits


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "OPS-data/07_astronomy_kepler/fits_lightcurves"
OUTPUT_DIR = ROOT / "OPS-data-main9/03_astronomy_kepler"
TARGET = 2_097_152
MIN_SEQUENCE = 100_000


def main() -> None:
    groups = defaultdict(list)
    for path in sorted(SOURCE_DIR.glob("*.fits")):
        match = re.match(r"(kplr\d+)-", path.name)
        if match:
            groups[match.group(1)].append(path)

    selected = []
    boundaries = []
    total = 0
    for target, paths in sorted(groups.items()):
        chunks = []
        for path in paths:
            with fits.open(path, memmap=True) as hdus:
                table = hdus[1].data
                time = np.asarray(table["TIME"], dtype=np.float64)
                flux = np.asarray(table["PDCSAP_FLUX"], dtype=np.float64)
                quality = np.asarray(table["SAP_QUALITY"])
                keep = (quality == 0) & np.isfinite(time) & np.isfinite(flux)
                chunks.append((time[keep], flux[keep]))
        if not chunks:
            continue
        time = np.concatenate([chunk[0] for chunk in chunks])
        flux = np.concatenate([chunk[1] for chunk in chunks])
        order = np.argsort(time, kind="stable")
        flux = flux[order]
        if len(flux) < MIN_SEQUENCE:
            continue
        take = min(len(flux), TARGET - total)
        if take < MIN_SEQUENCE:
            break
        selected.append(np.asarray(flux[:take], dtype="<f8"))
        boundaries.append({"target": target, "start": total, "length": take})
        total += take
        if total == TARGET:
            break

    if total < int(TARGET * 0.95):
        raise RuntimeError(f"only found {total} usable values, need approximately {TARGET}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / "03_astronomy_kepler_approx16MiB.f64"
    np.concatenate(selected).tofile(output)
    metadata = {
        "source": "https://archive.stsci.edu/pub/kepler/lightcurves/tarfiles/Q5_public/public_Q5_short_1.tgz",
        "domain": "astronomy",
        "variable": "PDCSAP_FLUX",
        "selection": "quality-zero finite samples, ordered by TIME within each target",
        "values": total,
        "bytes": output.stat().st_size,
        "format": "headerless little-endian float64",
        "boundaries": boundaries,
    }
    (OUTPUT_DIR / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
