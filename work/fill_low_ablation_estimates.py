#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "work/run_all_ops_algorithm.py"
SOURCE = ROOT / "outputs/final8-ablation-metrics"
OUT = ROOT / "outputs/final8-ablation-low-estimates"
ALGORITHMS = ["OPS-SPF", "OPS-ISC", "OPS-PF", "OPS-Enum", "OPS-NoReuse", "EFO-OPS", "OPF-OPS", "SOPP-OPS", "OPST-OPS", "OPS-Miner"]
DATASETS = [
    ("SDB1", ROOT/"work/sdb1-8-f64/SDB1_GOOG.f64", None, 1000, 100, 4, 45),
    ("SDB2", ROOT/"OPS-data-main9/05_physics_ligo/05_physics_ligo_128MiB.f64", 48204, 4422, 442, 4, 100),
    ("SDB3", ROOT/"OPS-data-main9/01_industrial_cwru/01_industrial_cwru_800KB.f64", None, 15000, 1500, 4, 57),
    ("SDB4", ROOT/"OPS-data-main9/04_biomedical_sleep_edf/04_biomedical_sleep_edf_approx64MiB.f64", 420551, 16000, 1600, 4, 253),
    ("SDB5", ROOT/"OPS-data-main9/02_weather_noaa_uscrn/02_weather_noaa_uscrn_4MiB.f64", None, 50000, 5000, 8, 95),
    ("SDB6", ROOT/"OPS-data-main9/03_astronomy_kepler/03_astronomy_kepler_approx16MiB.f64", "kepler", 20000, 2000, 8, 850),
    ("SDB7", ROOT/"OPS-data/05_transport_nyc_tlc/05_transport_nyc_tlc_640MiB.f64", 2009000, 60000, 6000, 8, 325),
    ("SDB8", ROOT/"OPS-data-main9/06_power_blond250/06_power_blond250_256MiB.f64", 4000000, 40000, 4000, 8, 991),
]

OUT.mkdir(parents=True, exist_ok=True)
summary = []
for alg in ALGORITHMS:
    for name, data, boundary, window, step, minsup, windows in DATASETS:
        measured = SOURCE/alg/f"{name}-timing.json"
        if measured.exists():
            r = json.loads(measured.read_text())
            summary.append({"algorithm":alg,"dataset":name,"status":"measured","seconds":r["elapsed_seconds"]})
            continue
        folder = OUT/alg
        folder.mkdir(parents=True, exist_ok=True)
        first = folder/f"{name}-first-window.json"
        if boundary == "kepler":
            metadata = ROOT/"OPS-data-main9/03_astronomy_kepler/metadata.json"
        elif isinstance(boundary, int):
            metadata = OUT/f"{name}-metadata.json"
            metadata.write_text(json.dumps({"boundaries":[{"start":0,"length":boundary}]})+"\n")
        else:
            metadata = None
        if not first.exists():
            cmd=[sys.executable,str(RUNNER),f"--algorithm={alg}","--dataset",str(data),"--window",str(window),"--step",str(step),"--minsup",str(minsup),"--max-windows","1","--output",str(first)]
            if metadata: cmd += ["--metadata",str(metadata)]
            subprocess.run(cmd,cwd=ROOT,check=True,capture_output=True,text=True)
        r=json.loads(first.read_text())
        summary.append({"algorithm":alg,"dataset":name,"status":"estimated","seconds":r["elapsed_seconds"]*windows,"first_window_seconds":r["elapsed_seconds"],"windows":windows})
        print(alg,name,summary[-1]["seconds"],flush=True)
(OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
