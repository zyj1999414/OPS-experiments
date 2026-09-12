#!/usr/bin/env python3
import argparse, importlib.util, json, time
from pathlib import Path
import numpy as np

SOURCE=Path('/Users/zyj/Documents/Codex/2026-08-18/users-zyj-documents-codex-2026-08/OPS-ablation/OPS-Miner.py')
spec=importlib.util.spec_from_file_location('ops_miner_user',SOURCE)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

def main():
 p=argparse.ArgumentParser();p.add_argument('dataset',type=Path);p.add_argument('--window',type=int,required=True);p.add_argument('--step',type=int,required=True);p.add_argument('--minsup',type=int,required=True);p.add_argument('--updates',type=int);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 values=np.memmap(a.dataset,dtype='<f8',mode='r')
 alg=mod.L2IncrementalPPCNewsup(a.window,a.step,a.minsup)
 start=time.perf_counter();result=alg.find2(values);updates=0
 pattern_total=sum(map(len,result))
 pattern_min=pattern_total
 pattern_max=pattern_total
 while a.updates is None or updates<a.updates:
  nxt=alg.find2()
  if nxt is None:break
  result=nxt;updates+=1
  count=sum(map(len,result))
  pattern_total+=count
  pattern_min=min(pattern_min,count)
  pattern_max=max(pattern_max,count)
 elapsed=time.perf_counter()-start
 summary={'dataset':str(a.dataset),'source_code':str(SOURCE),'data_length':len(values),'window':a.window,'step':a.step,'minsup':a.minsup,'updates':updates,'windows':updates+1,'elapsed_seconds':elapsed,'initial_seconds':alg.initial_runtime,'mean_update_seconds':float(np.mean(alg.update_runtimes)) if alg.update_runtimes else None,'level_counts_last_window':[len(x) for x in result],'patterns_last_window':sum(map(len,result)),'patterns_total_across_windows':pattern_total,'patterns_mean_per_window':pattern_total/(updates+1),'patterns_min_per_window':pattern_min,'patterns_max_per_window':pattern_max}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
