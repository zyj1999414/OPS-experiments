import json
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'work/run_all_ops_algorithm.py'
DATA = ROOT / 'OPS-data-main9/06_power_blond250/06_power_blond250_256MiB.f64'
OUT = ROOT / 'outputs/ops-scalability-100k-800k'
LENGTHS = [100_000, 200_000, 400_000, 800_000]
REPEATS = 5

OUT.mkdir(parents=True, exist_ok=True)
summary=[]
for length in LENGTHS:
    metadata=OUT/f'metadata-{length}.json'
    metadata.write_text(json.dumps({'boundaries':[{'start':0,'length':length}]})+'\n')
    records=[]
    for repeat in range(1,REPEATS+1):
        result=OUT/f'{length}-run{repeat}.json'
        command=[sys.executable,str(RUNNER),'--algorithm=OPS-Miner','--dataset',str(DATA),
                 '--metadata',str(metadata),'--window','20000','--step','2000',
                 '--minsup','8','--output',str(result)]
        completed=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        if completed.returncode:
            raise RuntimeError(completed.stdout+'\n'+completed.stderr)
        records.append(json.loads(result.read_text()))
    patterns={r['patterns_total'] for r in records}
    if len(patterns)!=1:
        raise RuntimeError(f'inconsistent results at {length}: {patterns}')
    times=[r['elapsed_seconds'] for r in records]
    row={'length':length,'window':20000,'step':2000,'overlap':'90%','minsup':8,
         'windows':records[0]['windows'],'runtimes_seconds':times,
         'median_runtime_seconds':statistics.median(times),
         'mean_runtime_seconds':statistics.mean(times),
         'patterns_total':records[0]['patterns_total'],
         'patterns_mean_per_window':records[0]['patterns_mean_per_window']}
    summary.append(row)
    print(json.dumps(row),flush=True)
summary_record={'dataset':'BLOND-250 Electric Current','repeats':REPEATS,'rows':summary,
                'ratio_800k_over_100k':summary[-1]['median_runtime_seconds']/summary[0]['median_runtime_seconds']}
(OUT/'summary.json').write_text(json.dumps(summary_record,indent=2)+'\n')
print(json.dumps(summary_record),flush=True)
