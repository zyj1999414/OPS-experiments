#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "work/run_all_ops_algorithm.py"
OUT = ROOT / "outputs/final-compact-sdb1-8-ablation"

ALGORITHMS = [
    "OPS-SPF", "OPS-ISC", "OPS-PF", "OPS-Enum", "OPS-NoReuse",
    "EFO-OPS", "OPF-OPS", "SOPP-OPS", "OPST-OPS", "OPS-Miner",
]

DATASETS = [
    ("SDB1", ROOT / "work/sdb1-8-f64/SDB1_GOOG.f64", 5_484, 1_000, 100, 40, 45),
    ("SDB2", ROOT / "OPS-data-main9/05_physics_ligo/05_physics_ligo_128MiB.f64", 22_000, 4_422, 442, 40, 40),
    ("SDB3", ROOT / "OPS-data-main9/01_industrial_cwru/01_industrial_cwru_800KB.f64", 57_000, 15_000, 1_500, 40, 29),
    ("SDB4", ROOT / "OPS-data-main9/04_biomedical_sleep_edf/04_biomedical_sleep_edf_approx64MiB.f64", 108_000, 16_000, 1_600, 40, 58),
    ("SDB5", ROOT / "OPS-data-main9/02_weather_noaa_uscrn/02_weather_noaa_uscrn_4MiB.f64", 190_000, 50_000, 5_000, 80, 29),
    ("SDB6", ROOT / "OPS-data-main9/03_astronomy_kepler/03_astronomy_kepler_approx16MiB.f64", 330_000, 50_000, 5_000, 80, 57),
    ("SDB7", ROOT / "OPS-data/05_transport_nyc_tlc/05_transport_nyc_tlc_640MiB.f64", 520_000, 60_000, 6_000, 80, 77),
    ("SDB8", ROOT / "OPS-data-main9/06_power_blond250/06_power_blond250_256MiB.f64", 900_000, 70_000, 7_000, 80, 119),
]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, _data, length, *_ in DATASETS:
        save(OUT / "metadata" / f"{name}.json", {"boundaries": [{"start": 0, "length": length}]})

    for algorithm in ALGORITHMS:
        for name, data, _length, window, step, minsup, windows in DATASETS:
            result = OUT / algorithm / f"{name}.json"
            if result.exists():
                print("SKIP", algorithm, name, flush=True)
                continue
            log = OUT / algorithm / f"{name}.log"
            pending = OUT / algorithm / f"{name}.pending.json"
            result.parent.mkdir(parents=True, exist_ok=True)
            command = [
                sys.executable, str(RUNNER), "--algorithm", algorithm,
                "--dataset", str(data), "--metadata", str(OUT / "metadata" / f"{name}.json"),
                "--window", str(window), "--step", str(step), "--minsup", str(minsup),
                "--max-windows", str(windows), "--count-candidates", "--output", str(pending),
            ]
            print("START", algorithm, name, flush=True)
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            log.write_text(completed.stdout + "\n" + completed.stderr)
            if completed.returncode:
                print("FAILED", algorithm, name, completed.returncode, flush=True)
                continue
            pending.replace(result)
            measured = json.loads(result.read_text())
            print(
                "DONE", algorithm, name,
                f"{measured['elapsed_seconds']:.6f}s",
                f"{measured['peak_rss_mib']:.2f}MiB",
                flush=True,
            )
    print("ALL_DONE", flush=True)


if __name__ == "__main__":
    main()
