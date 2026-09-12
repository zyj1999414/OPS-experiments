import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUNNER=ROOT/'work/run_original_efo_sopp_first_window.py'
WINDOWS=[1000,4422,15000,16000,50000,50000,60000,200000]
MINSUPS=[40,40,40,80,80,80,80,80]
OUT=ROOT/'outputs/original-efo-sopp-main8-first-window-logs';OUT.mkdir(parents=True,exist_ok=True)
for algorithm in ['EFO-Miner','SOPP-Miner']:
    for i,(window,minsup) in enumerate(zip(WINDOWS,MINSUPS),1):
        print('START',algorithm,f'SDB{i}',flush=True)
        command=[sys.executable,str(RUNNER),'--algorithm',algorithm,'--dataset',f'SDB{i}',
                 '--window-size',str(window),'--minsup',str(minsup)]
        completed=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        (OUT/f'{algorithm}-SDB{i}.log').write_text(completed.stdout+'\n'+completed.stderr)
        if completed.returncode:raise RuntimeError(f'failed {algorithm} SDB{i}')
        print('DONE',algorithm,f'SDB{i}',completed.stdout.strip().splitlines()[-1],flush=True)
