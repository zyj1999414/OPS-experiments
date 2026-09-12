#!/usr/bin/env python3
import importlib.util, json, resource, time
from pathlib import Path
import numpy as np
from astropy.io import fits
SOURCE=Path('/Users/zyj/Documents/Codex/2026-08-18/users-zyj-documents-codex-2026-08/OPS-ablation/OPS-Miner.py')
spec=importlib.util.spec_from_file_location('ops_miner_user',SOURCE);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
root=Path(__file__).resolve().parents[1]; files=sorted((root/'OPS-data/07_astronomy_kepler/fits_lightcurves').glob('*.fits'))
W,S,MS=10000,1000,100; start=time.perf_counter(); total_values=total_windows=total_updates=0; processed=0; skipped=0; last_counts=[]; update_times=[];pattern_total=0;pattern_min=None;pattern_max=None
for p in files:
 with fits.open(p,memmap=True) as h:
  tab=h[1].data;x=np.asarray(tab['PDCSAP_FLUX']);q=np.asarray(tab['SAP_QUALITY']);x=np.ascontiguousarray(x[(q==0)&np.isfinite(x)],dtype=np.float64)
 total_values+=len(x)
 if len(x)<W:skipped+=1;continue
 alg=mod.L2IncrementalPPCNewsup(W,S,MS);result=alg.find2(x);updates=0
 count=sum(map(len,result));pattern_total+=count;pattern_min=count if pattern_min is None else min(pattern_min,count);pattern_max=count if pattern_max is None else max(pattern_max,count)
 while True:
  nxt=alg.find2()
  if nxt is None:break
  result=nxt;updates+=1;count=sum(map(len,result));pattern_total+=count;pattern_min=min(pattern_min,count);pattern_max=max(pattern_max,count)
 processed+=1;total_updates+=updates;total_windows+=updates+1;last_counts.append([len(y) for y in result]);update_times.extend(alg.update_runtimes)
summary={'dataset':str(root/'OPS-data/07_astronomy_kepler/fits_lightcurves'),'source_code':str(SOURCE),'fits_files':len(files),'processed_files':processed,'skipped_short_files':skipped,'valid_data_length':total_values,'window':W,'step':S,'minsup':MS,'updates':total_updates,'windows':total_windows,'elapsed_seconds':time.perf_counter()-start,'mean_update_seconds':float(np.mean(update_times)) if update_times else None,'patterns_total':pattern_total,'patterns_mean_per_window':pattern_total/total_windows if total_windows else None,'patterns_min_per_window':pattern_min,'patterns_max_per_window':pattern_max,'patterns_in_last_window_per_series_sum':sum(sum(x) for x in last_counts),'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1048576}
out=root/'outputs/OPS-Miner-results/07_kepler.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))
