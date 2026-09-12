import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];RUNNER=ROOT/'work/run_all_ops_algorithm.py'
OUT=ROOT/'outputs/ecg-scale-one-window-ops-minsup10';OUT.mkdir(parents=True,exist_ok=True)
N=22_973_535
DATASETS={
 'NOAA':ROOT/'OPS-data/04_weather_noaa_isd/04_weather_noaa_isd_512MiB.f64',
 'Binance':ROOT/'OPS-data-main9/07_finance_binance/07_finance_binance_512MiB.f64',
 'NYC-TLC':ROOT/'OPS-data/05_transport_nyc_tlc/05_transport_nyc_tlc_640MiB.f64',
 'BLOND-250':ROOT/'OPS-data-main9/06_power_blond250/06_power_blond250_256MiB.f64',
 'Sleep-EDF':ROOT/'OPS-data/03_biomedical_sleep_edf/03_biomedical_sleep_edf_384MiB.f64',
 'LibriSpeech':ROOT/'OPS-data/02_speech_librispeech/02_speech_librispeech_256MiB.f64',
 'LIGO-GWOSC':ROOT/'OPS-data/08_physics_ligo_gwosc/08_physics_ligo_gwosc_1024MiB.f64',
 'EarthScope':ROOT/'OPS-data-main9/08_seismic_earthscope/08_seismic_earthscope_1GiB.f64'}
metadata=OUT/'metadata.json';metadata.write_text(json.dumps({'boundaries':[{'start':0,'length':N}]})+'\n')
for name,path in DATASETS.items():
 result=OUT/f'{name}.json'
 if result.exists():print('SKIP',name,flush=True);continue
 cmd=[sys.executable,str(RUNNER),'--algorithm=OPS-Miner','--dataset',str(path),'--metadata',str(metadata),
      '--window',str(N),'--step',str(N),'--minsup','10','--output',str(result)]
 print('START',name,flush=True)
 p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
 (OUT/f'{name}.log').write_text(p.stdout+'\n'+p.stderr)
 if p.returncode:raise RuntimeError(f'{name} failed with {p.returncode}; inspect log')
 r=json.loads(result.read_text());print('DONE',name,r['elapsed_seconds'],r['peak_rss_mib'],r['patterns_total'],flush=True)
