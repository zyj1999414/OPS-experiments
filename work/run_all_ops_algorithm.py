#!/usr/bin/env python3
import argparse, importlib.util, json, resource, sys, time, types
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'algorithms/OPS-ablation'
SPECS={
 'OPS-Miner':(ROOT/'work/run_cached_fusion_ops_miner.py','ScanAndFusionReuseMiner','incremental'),
 '-1OPS-Miner':(BASE/'OPS-Miner.py','L2IncrementalPPCNewsup','incremental'),
 'OPS-NoReuse':('OPS-NoReuse.py','OPSNoReuseMiner','incremental'),
 'OPS-NoNumpy':('OPS-NoNumpy.py','OPSNoNumpyMiner','incremental_list'),
 'OPS-PF':('OPS-PF.py','OPSPFMiner','incremental'),
 'OPS-Enum':('OPS-Enum.py','OPSEnumMiner','incremental'),
 'OPS-ISC':('OPS-ISC.py','OPSISC','stateful'),
 'OPS-SPF':('OPS-SPF.py','OPSSPF','stateful'),
 'EFO-OPS':('EFO-OPS.py','EFOOPS','window_frequent'),
 'OPF-OPS':('OPF-OPS.py','OPFOPS','window_frequent'),
 'SOPP-OPS':('SOPP-OPS.py','SOPPOPS','window_frequent'),
 'OPST-OPS':('OPST-OPS/OPST-OPS.py','OPSTOPS','window_maximal'),
}

def load(name,path):
 if name=='OPF-OPS' and 'zmq.utils' not in sys.modules:
  zmq=types.ModuleType('zmq');utils=types.ModuleType('zmq.utils');utils.monitor=None;zmq.utils=utils;sys.modules['zmq']=zmq;sys.modules['zmq.utils']=utils
 if name=='SOPP-OPS' and 'memory_profiler' not in sys.modules:
  mp=types.ModuleType('memory_profiler');mp.memory_usage=lambda *args,**kwargs: [];sys.modules['memory_profiler']=mp
 if name=='OPST-OPS':sys.path.insert(0,str(BASE/'OPST-OPS'))
 spec=importlib.util.spec_from_file_location('bench_'+name.replace('-','_'),path)
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def add(stats,count,candidates=None):
 stats['windows']+=1;stats['patterns_total']+=int(count);stats['patterns_min']=int(count) if stats['patterns_min'] is None else min(stats['patterns_min'],int(count));stats['patterns_max']=int(count) if stats['patterns_max'] is None else max(stats['patterns_max'],int(count))
 if candidates is not None:stats['candidates_total']+=int(candidates)

def instrument_candidates(algorithm,instance):
 counter={'value':0}
 if algorithm=='OPS-Enum':
  original=instance._build_fusion_table
  def wrapped(*args,**kwargs):
   transitions=original(*args,**kwargs)
   counter['value']+=len({x for x in transitions.values() if x is not None})
   return transitions
  instance._build_fusion_table=wrapped
 elif algorithm!='OPS-Miner':
  original=instance.frequent_pattern_fusion
  def wrapped(*args,**kwargs):
   candidate=original(*args,**kwargs)
   if candidate is not None:counter['value']+=1
   return candidate
  instance.frequent_pattern_fusion=wrapped
 return counter

def main():
 p=argparse.ArgumentParser();p.add_argument('--algorithm',choices=SPECS,required=True);p.add_argument('--dataset',type=Path,required=True);p.add_argument('--metadata',type=Path);p.add_argument('--window',type=int,required=True);p.add_argument('--step',type=int,required=True);p.add_argument('--minsup',type=int,required=True);p.add_argument('--max-windows',type=int);p.add_argument('--count-candidates',action='store_true');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 source,clsname,kind=SPECS[a.algorithm]
 source=source if isinstance(source,Path) else BASE/source
 mod=load(a.algorithm,source);cls=getattr(mod,clsname);raw=np.memmap(a.dataset,dtype='<f8',mode='r')
 metadata=json.loads(a.metadata.read_text()) if a.metadata else {}
 boundaries=metadata.get('boundaries') or [{'start':0,'length':len(raw)}]
 native_candidates=kind in {'stateful','window_frequent'}
 stats={'algorithm':a.algorithm,'dataset':str(a.dataset),'data_length':len(raw),'source_series':len(boundaries),'window':a.window,'step':a.step,'minsup':a.minsup,'count_semantics':'maximal frequent patterns' if kind=='window_maximal' else 'frequent patterns','windows':0,'patterns_total':0,'patterns_min':None,'patterns_max':None,'candidates_total':0 if kind!='window_maximal' and (a.count_candidates or native_candidates) else None}
 start=time.perf_counter()
 for boundary in boundaries:
  if a.max_windows is not None and stats['windows']>=a.max_windows:break
  begin=int(boundary['start']);length=int(boundary['length'])
  if length<a.window:continue
  data=raw[begin:begin+length]
  if kind.startswith('incremental'):
   if kind=='incremental_list':data=list(data)
   alg=cls(a.window,a.step,a.minsup);candidate_counter=instrument_candidates(a.algorithm,alg) if a.count_candidates else {'value':0};result=alg.find2(data);add(stats,sum(map(len,result)),2+candidate_counter['value'] if a.count_candidates else None)
   previous_candidates=candidate_counter['value']
   while a.max_windows is None or stats['windows']<a.max_windows:
    result=alg.find2()
    if result is None:break
    current_candidates=candidate_counter['value'];add(stats,sum(map(len,result)),2+current_candidates-previous_candidates if a.count_candidates else None);previous_candidates=current_candidates
   if a.count_candidates and a.algorithm=='OPS-Miner':
    # Only cache misses materialize a new fused pattern. Cache hits reuse it.
    stats['candidates_total']-=2*stats['windows']
    stats['candidates_total']+=2*stats['windows']+sum(x is not None for x in alg.fusion_cache.values())
  elif kind=='stateful':
   mod.read_file=lambda _path, segment=data:segment
   alg=cls('MEMMAP',a.window,a.step,a.minsup);first=True
   while a.max_windows is None or stats['windows']<a.max_windows:
    result=alg.solve_window(True) if first else alg.slide();first=False
    if result is None:break
    add(stats,result['frequent_patterns'],result['candidate_patterns'])
  else:
   alg=cls(a.window,a.step,a.minsup);left=0
   while left+a.window<=len(data) and (a.max_windows is None or stats['windows']<a.max_windows):
    window_data=data[left:left+a.window]
    if kind=='window_maximal':
     # OPST's wavelet tree requires Python integers. Dense ranking preserves
     # all order and tie relations used by order-preserving pattern mining.
     window_data=(np.unique(window_data,return_inverse=True)[1]+1).tolist()
    result=alg.mine_window(window_data)
    key='maximal_count' if kind=='window_maximal' else 'frequent'
    add(stats,result[key],result.get('candidates') if kind!='window_maximal' else None);left+=a.step
 stats['elapsed_seconds']=time.perf_counter()-start;stats['patterns_mean_per_window']=stats['patterns_total']/stats['windows'] if stats['windows'] else None;stats['peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;stats['peak_rss_mib']=stats['peak_rss_bytes']/1048576
 stats['candidates_mean_per_window']=stats['candidates_total']/stats['windows'] if stats['windows'] and stats['candidates_total'] is not None else None
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n');print(json.dumps(stats,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
