import json
import subprocess
import sys
from pathlib import Path
from run_final8_ablation_metrics import ROOT, RUNNER, ALGORITHMS, DATASETS

params = [(1000,100,4,45),(4422,442,4,100),(15000,1500,4,57),
          (16000,1600,8,253),(50000,5000,8,95),(50000,5000,20,248),
          (60000,6000,20,325),(200000,20000,40,191)]
out = ROOT / 'outputs/first-window-estimates-latest'
out.mkdir(parents=True, exist_ok=True)
for alg in ALGORITHMS:
    for dataset, param in zip(DATASETS, params):
        name, source, metadata, *_ = dataset
        w,s,m,k = param
        target = out / f'{alg}-{name}.json'
        if target.exists():
            continue
        command = [sys.executable,str(RUNNER),f'--algorithm={alg}',
                   '--dataset',str(ROOT/source),'--window',str(w),'--step',str(s),
                   '--minsup',str(m),'--max-windows','1','--output',str(target)]
        if metadata:
            command += ['--metadata',str(ROOT/metadata)]
        print('START',alg,name,flush=True)
        result = subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        if result.returncode:
            target.with_suffix('.error.txt').write_text(result.stdout+'\n'+result.stderr)
            print('ERROR',alg,name,flush=True)
            continue
        record=json.loads(target.read_text())
        assert record['windows']==1
        record['estimated_windows']=k
        record['estimated_total_seconds']=record['elapsed_seconds']*k
        target.write_text(json.dumps(record,indent=2)+'\n')
        print('DONE',alg,name,record['elapsed_seconds'],record['estimated_total_seconds'],flush=True)
