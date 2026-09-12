"""Sequential, resumable latest-parameter run; SDB8 last, fastest first."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from run_final8_ablation_metrics import ROOT, RUNNER, ALGORITHMS, DATASETS

OUT = ROOT / 'outputs/latest-full-ablation'
PARAMS = [(1000,100,4,45),(4422,442,4,100),(15000,1500,4,57),
          (16000,1600,8,253),(50000,5000,8,95),(50000,5000,20,248),
          (60000,6000,20,325),(200000,20000,40,191)]
SDB8_ORDER = ['OPS-NoReuse','OPS-Miner','OPS-Enum','SOPP-OPS','OPST-OPS',
              'OPS-PF','OPS-ISC','OPF-OPS','EFO-OPS','OPS-SPF']

def save(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [(alg,i) for alg in ALGORITHMS for i in range(7)]
    jobs += [(alg,7) for alg in SDB8_ORDER]
    save(OUT/'manifest.json', {'parameters':PARAMS,'datasets':DATASETS,
         'jobs':jobs,'timeout':None,'timing':'independent process; extra candidate wrappers disabled'})
    for alg,i in jobs:
        name,source,metadata,prefix,*_ = DATASETS[i]
        w,s,m,k = PARAMS[i]
        folder = OUT/alg
        folder.mkdir(exist_ok=True)
        if prefix is not None:
            metadata_path = OUT/f'{name}-metadata.json'
            save(metadata_path, {'boundaries':[{'start':0,'length':prefix}]})
        else:
            metadata_path = ROOT/metadata if metadata else None
        base = [sys.executable,str(RUNNER),f'--algorithm={alg}','--dataset',str(ROOT/source),
                '--window',str(w),'--step',str(s),'--minsup',str(m)]
        if metadata_path:
            base += ['--metadata',str(metadata_path)]
        phases = [('timing',False)]
        if alg in {'OPS-Miner','OPS-NoReuse','OPS-PF','OPS-Enum'}:
            phases.append(('candidates',True))
        for phase,count in phases:
            result = folder/f'{name}-{phase}.json'
            if result.exists():
                record=json.loads(result.read_text())
                if record.get('windows') == k:
                    print('SKIP',alg,name,phase,flush=True)
                    continue
                raise RuntimeError(f'Existing result has wrong window count: {result}')
            partial = folder/f'{name}-{phase}.pending.json'
            command = base + (['--count-candidates'] if count else []) + ['--output',str(partial)]
            state={'algorithm':alg,'dataset':name,'phase':phase,'status':'running','started_unix':time.time()}
            save(OUT/'status.json',state)
            print('START',alg,name,phase,flush=True)
            with (folder/f'{name}-{phase}.log').open('w') as log:
                completed=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            if completed.returncode:
                state.update(status='error',returncode=completed.returncode)
                save(OUT/'status.json',state)
                raise RuntimeError(f'Failed: {alg} {name} {phase}; inspect log')
            record=json.loads(partial.read_text())
            if record['windows']!=k:
                raise RuntimeError(f'Window count mismatch: {alg} {name}')
            save(result,record)
            state.update(status='completed',elapsed_seconds=record['elapsed_seconds'])
            save(OUT/'status.json',state)
            print('DONE',alg,name,phase,record['elapsed_seconds'],record['peak_rss_mib'],flush=True)
    save(OUT/'status.json',{'status':'all_completed','finished_unix':time.time()})
    print('ALL COMPLETED',flush=True)

if __name__=='__main__':
    main()
