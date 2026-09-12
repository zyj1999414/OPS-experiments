#!/usr/bin/env python3
import argparse, json, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PY='/Users/zyj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'
ALGS=['OPS-Miner','-1OPS-Miner','OPS-NoReuse','OPS-NoNumpy','OPS-PF','OPS-Enum','OPS-ISC','OPS-SPF','EFO-OPS','OPF-OPS','SOPP-OPS','OPST-OPS']
DATA=[
 ('01_finance','OPS-data/01_finance_binance/01_finance_binance_64MiB.f64',100000,10000,1000),
 ('02_speech','OPS-data/02_speech_librispeech/02_speech_librispeech_256MiB.f64',16000,1600,160),
 ('03_eeg','OPS-data/03_biomedical_sleep_edf/03_biomedical_sleep_edf_384MiB.f64',3000,300,30),
 ('04_weather','OPS-data/04_weather_noaa_isd/04_weather_noaa_isd_512MiB.f64',200,20,2),
 ('05_transport','OPS-data/05_transport_nyc_tlc/05_transport_nyc_tlc_640MiB.f64',10000,1000,100),
 ('08_ligo','OPS-data/08_physics_ligo_gwosc/08_physics_ligo_gwosc_1024MiB.f64',409600,40960,4096),
]
p=argparse.ArgumentParser();p.add_argument('--worker',type=int,required=True);p.add_argument('--workers',type=int,default=3);a=p.parse_args()
jobs=[(d,alg,path,w,s,m) for d,path,w,s,m in DATA for alg in ALGS]
for idx,(d,alg,path,w,s,m) in enumerate(jobs):
 if idx%a.workers!=a.worker:continue
 out=ROOT/'outputs/OPS-ablation-benchmark'/d/f'{alg}.json'
 if out.exists():
  try:
   json.loads(out.read_text());print('SKIP',d,alg,flush=True);continue
  except:pass
 out.parent.mkdir(parents=True,exist_ok=True);cmd=[PY,str(ROOT/'work/run_all_ops_algorithm.py'),f'--algorithm={alg}','--dataset',str(ROOT/path),'--window',str(w),'--step',str(s),'--minsup',str(m),'--output',str(out)]
 print('START',d,alg,flush=True);start=time.time();r=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
 if r.returncode:
  err=out.with_suffix('.error.txt');err.write_text(r.stdout+'\n'+r.stderr);print('ERROR',d,alg,err,flush=True)
 else:
  result=json.loads(out.read_text());print('DONE',d,alg,round(time.time()-start,2),result['windows'],round(result['patterns_mean_per_window'],3),round(result['peak_rss_mib'],2),flush=True)
