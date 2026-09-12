#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUNNER=ROOT/'work/run_all_ops_algorithm.py'
OUT=ROOT/'outputs/final-sdb1-8-candidate-counts'
ALGORITHMS=['OPS-PF','OPS-Enum','OPS-NoReuse','OPS-Miner']
DATASETS=[
 ('SDB1',ROOT/'work/sdb1-8-f64/SDB1_GOOG.f64',None,1000,100,40,45),
 ('SDB2',ROOT/'OPS-data-main9/05_physics_ligo/05_physics_ligo_128MiB.f64',ROOT/'outputs/sdb1-7-high-minsup-all-ablation/metadata/SDB2.json',4422,442,40,100),
 ('SDB3',ROOT/'OPS-data-main9/01_industrial_cwru/01_industrial_cwru_800KB.f64',None,15000,1500,40,57),
 ('SDB4',ROOT/'OPS-data-main9/04_biomedical_sleep_edf/04_biomedical_sleep_edf_approx64MiB.f64',ROOT/'outputs/sdb1-7-high-minsup-all-ablation/metadata/SDB4.json',16000,1600,40,253),
 ('SDB5',ROOT/'OPS-data-main9/02_weather_noaa_uscrn/02_weather_noaa_uscrn_4MiB.f64',None,50000,5000,80,95),
 ('SDB6',ROOT/'OPS-data-main9/03_astronomy_kepler/03_astronomy_kepler_approx16MiB.f64',ROOT/'work/new_n_sdb6_metadata.json',50000,5000,80,111),
 ('SDB7',ROOT/'OPS-data/05_transport_nyc_tlc/05_transport_nyc_tlc_640MiB.f64',ROOT/'work/new_n_sdb7_metadata.json',60000,6000,80,116),
 ('SDB8',ROOT/'OPS-data-main9/06_power_blond250/06_power_blond250_256MiB.f64',ROOT/'work/new_n_sdb8_metadata.json',70000,7000,80,119),
]
for alg in ALGORITHMS:
 for name,data,meta,w,s,m,k in DATASETS:
  out=OUT/alg/f'{name}.json';out.parent.mkdir(parents=True,exist_ok=True)
  if out.exists(): print('SKIP',alg,name,flush=True);continue
  cmd=[sys.executable,str(RUNNER),f'--algorithm={alg}','--dataset',str(data),'--window',str(w),'--step',str(s),'--minsup',str(m),'--max-windows',str(k),'--count-candidates','--output',str(out)]
  if meta:cmd+=['--metadata',str(meta)]
  print('START',alg,name,flush=True)
  subprocess.run(cmd,cwd=ROOT,check=True,capture_output=True,text=True)
  r=json.loads(out.read_text());print('DONE',alg,name,r['candidates_total'],flush=True)
