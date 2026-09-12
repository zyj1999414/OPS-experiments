import json,subprocess,sys
from pathlib import Path
from run_final8_ablation_metrics import ROOT,RUNNER,DATASETS
OUT=ROOT/'outputs/sdb6-8-minsup100-ops-compare';OUT.mkdir(parents=True,exist_ok=True)
PARAMS={6:(50000,5000,248),7:(60000,6000,325),8:(200000,20000,191)}
for alg in ['OPS-Miner','OPS-NoReuse']:
    folder=OUT/alg;folder.mkdir(exist_ok=True)
    for i,(w,s,k) in PARAMS.items():
        _,source,metadata,prefix,*_=DATASETS[i-1]
        if prefix is not None:
            meta=OUT/f'SDB{i}-metadata.json';meta.write_text(json.dumps({'boundaries':[{'start':0,'length':prefix}]})+'\n')
        else:meta=ROOT/metadata if metadata else None
        for phase,count in [('timing',False),('candidates',True)]:
            result=folder/f'SDB{i}-{phase}.json'
            cmd=[sys.executable,str(RUNNER),f'--algorithm={alg}','--dataset',str(ROOT/source),
                 '--window',str(w),'--step',str(s),'--minsup','100']
            if meta:cmd+=['--metadata',str(meta)]
            if count:cmd+=['--count-candidates']
            cmd+=['--output',str(result)]
            p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
            if p.returncode:raise RuntimeError(p.stdout+'\n'+p.stderr)
            r=json.loads(result.read_text());assert r['windows']==k
            print(alg,f'SDB{i}',phase,r['elapsed_seconds'],r['peak_rss_mib'],r['patterns_total'],r['candidates_total'],flush=True)
