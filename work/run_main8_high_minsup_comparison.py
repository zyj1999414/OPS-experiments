import json
import subprocess
import sys
from pathlib import Path
from run_final8_ablation_metrics import ROOT, RUNNER, DATASETS

OUT=ROOT/'outputs/main8-high-minsup-comparison';OUT.mkdir(parents=True,exist_ok=True)
PARAMS=[(1000,100,40,45),(4422,442,40,100),(15000,1500,40,57),(16000,1600,40,253),
        (50000,5000,80,95),(50000,5000,80,248),(60000,6000,80,325),(200000,20000,80,191)]
for algorithm in ['OPS-Miner','OPS-NoReuse']:
    folder=OUT/algorithm;folder.mkdir(exist_ok=True)
    for i,(dataset,param) in enumerate(zip(DATASETS,PARAMS),1):
        name,source,metadata,prefix,*_=dataset;w,s,m,k=param
        if prefix is not None:
            metadata_path=OUT/f'SDB{i}-metadata.json'
            metadata_path.write_text(json.dumps({'boundaries':[{'start':0,'length':prefix}]})+'\n')
        else:metadata_path=ROOT/metadata if metadata else None
        for phase,count in [('timing',False),('candidates',True)]:
            result=folder/f'SDB{i}-{phase}.json'
            command=[sys.executable,str(RUNNER),f'--algorithm={algorithm}','--dataset',str(ROOT/source),
                     '--window',str(w),'--step',str(s),'--minsup',str(m)]
            if metadata_path:command+=['--metadata',str(metadata_path)]
            if count:command+=['--count-candidates']
            command+=['--output',str(result)]
            print('START',algorithm,f'SDB{i}',phase,flush=True)
            completed=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            if completed.returncode:raise RuntimeError(completed.stdout+'\n'+completed.stderr)
            record=json.loads(result.read_text());assert record['windows']==k
            print('DONE',algorithm,f'SDB{i}',phase,record['elapsed_seconds'],record['peak_rss_mib'],record['patterns_total'],record['candidates_total'],flush=True)
