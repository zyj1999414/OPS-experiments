import json
import statistics
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUNNER=ROOT/'work/run_all_ops_algorithm.py'
DATA=ROOT/'OPS-data-main9/06_power_blond250/06_power_blond250_256MiB.f64'
OUT=ROOT/'outputs/ops-scalability-4mib-32mib-check-w50000'
OUT.mkdir(parents=True,exist_ok=True)
sizes=[4,32]
rows=[]
for size_mib in sizes:
    length=size_mib*1024*1024//8
    metadata=OUT/f'metadata-{size_mib}MiB.json'
    metadata.write_text(json.dumps({'boundaries':[{'start':0,'length':length}]})+'\n')
    records=[]
    for repeat in range(1,6):
        result=OUT/f'{size_mib}MiB-run{repeat}.json'
        command=[sys.executable,str(RUNNER),'--algorithm=OPS-Miner','--dataset',str(DATA),
                 '--metadata',str(metadata),'--window','50000','--step','5000',
                 '--minsup','20','--output',str(result)]
        completed=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        if completed.returncode:
            raise RuntimeError(completed.stdout+'\n'+completed.stderr)
        records.append(json.loads(result.read_text()))
    if len({r['patterns_total'] for r in records})!=1:
        raise RuntimeError('inconsistent pattern totals')
    times=[r['elapsed_seconds'] for r in records]
    row={'size_mib':size_mib,'length':length,'windows':records[0]['windows'],
         'runtimes_seconds':times,'median_runtime_seconds':statistics.median(times),
         'mean_runtime_seconds':statistics.mean(times),
         'median_peak_rss_mib':statistics.median(r['peak_rss_mib'] for r in records),
         'patterns_total':records[0]['patterns_total'],
         'patterns_mean_per_window':records[0]['patterns_mean_per_window']}
    rows.append(row)
    print(json.dumps(row),flush=True)
summary={'dataset':'BLOND-250 Electric Current','window':50000,'step':5000,
         'overlap':'90%','minsup':20,'repeats':5,'rows':rows,
         'runtime_ratio_32mib_over_4mib':rows[1]['median_runtime_seconds']/rows[0]['median_runtime_seconds'],
         'rss_ratio_32mib_over_4mib':rows[1]['median_peak_rss_mib']/rows[0]['median_peak_rss_mib']}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary),flush=True)
