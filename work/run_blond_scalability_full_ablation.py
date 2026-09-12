"""Full resumable ablation on BLOND prefixes from 4 to 32 MiB."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUNNER=ROOT/'work/run_all_ops_algorithm.py'
DATA=ROOT/'OPS-data-main9/06_power_blond250/06_power_blond250_256MiB.f64'
OUT=ROOT/'outputs/blond-scalability-full-ablation'
ALGORITHMS=['OPS-SPF','OPS-ISC','OPS-PF','OPS-Enum','OPS-NoReuse',
            'EFO-OPS','OPF-OPS','SOPP-OPS','OPST-OPS','OPS-Miner']
SIZES=list(range(4,33,4))

def save(path,obj):
    tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    tmp.replace(path)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    manifest={'dataset':'BLOND-250 Electric Current','sizes_mib':SIZES,
              'window':50000,'step':5000,'overlap':'90%','minsup':20,
              'algorithms':ALGORITHMS,'timeout':None}
    save(OUT/'manifest.json',manifest)
    for algorithm in ALGORITHMS:
        folder=OUT/algorithm;folder.mkdir(exist_ok=True)
        for size in SIZES:
            name=f'SDB{size//4}'
            length=size*1024*1024//8
            metadata=OUT/f'{name}-metadata.json'
            save(metadata,{'boundaries':[{'start':0,'length':length}]})
            expected=(length-50000)//5000+1
            phases=[('timing',False)]
            if algorithm in {'OPS-PF','OPS-Enum','OPS-NoReuse','OPS-Miner'}:
                phases.append(('candidates',True))
            for phase,count in phases:
                result=folder/f'{name}-{phase}.json'
                if result.exists() and json.loads(result.read_text()).get('windows')==expected:
                    print('SKIP',algorithm,name,phase,flush=True);continue
                pending=folder/f'{name}-{phase}.pending.json'
                command=[sys.executable,str(RUNNER),f'--algorithm={algorithm}','--dataset',str(DATA),
                         '--metadata',str(metadata),'--window','50000','--step','5000',
                         '--minsup','20']+(['--count-candidates'] if count else [])+['--output',str(pending)]
                state={'status':'running','algorithm':algorithm,'dataset':name,'size_mib':size,
                       'phase':phase,'started_unix':time.time()};save(OUT/'status.json',state)
                print('START',algorithm,name,phase,flush=True)
                with (folder/f'{name}-{phase}.log').open('w') as log:
                    proc=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
                if proc.returncode:
                    state.update(status='error',returncode=proc.returncode);save(OUT/'status.json',state)
                    raise RuntimeError(f'Failed {algorithm} {name} {phase}')
                record=json.loads(pending.read_text())
                if record['windows']!=expected:raise RuntimeError('window count mismatch')
                save(result,record)
                state.update(status='completed',elapsed_seconds=record['elapsed_seconds']);save(OUT/'status.json',state)
                print('DONE',algorithm,name,phase,record['elapsed_seconds'],record['peak_rss_mib'],flush=True)
    save(OUT/'status.json',{'status':'all_completed','finished_unix':time.time()})
    print('ALL COMPLETED',flush=True)

if __name__=='__main__':main()
