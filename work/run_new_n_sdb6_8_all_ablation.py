#!/usr/bin/env python3
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "work/run_all_ops_algorithm.py"
OUT = ROOT / "outputs/new-N-sdb6-8-all-ablation"
PRIOR = ROOT / "outputs/new-N-sdb6-8-ops-vs-noreuse"
ALGORITHMS = ["OPS-SPF", "OPS-ISC", "OPS-PF", "OPS-Enum", "OPS-NoReuse", "EFO-OPS", "OPF-OPS", "SOPP-OPS", "OPST-OPS", "OPS-Miner"]
DATASETS = [
    ("SDB6", ROOT/"OPS-data-main9/03_astronomy_kepler/03_astronomy_kepler_approx16MiB.f64", ROOT/"work/new_n_sdb6_metadata.json", 50000, 5000, 80, 111),
    ("SDB7", ROOT/"OPS-data/05_transport_nyc_tlc/05_transport_nyc_tlc_640MiB.f64", ROOT/"work/new_n_sdb7_metadata.json", 60000, 6000, 80, 116),
    ("SDB8", ROOT/"OPS-data-main9/06_power_blond250/06_power_blond250_256MiB.f64", ROOT/"work/new_n_sdb8_metadata.json", 70000, 7000, 80, 119),
]

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
    tmp.replace(path)

def cmd(alg,data,meta,w,s,k,out):
    return [sys.executable,str(RUNNER),f"--algorithm={alg}","--dataset",str(data),"--metadata",str(meta),"--window",str(w),"--step",str(s),"--minsup","80","--max-windows",str(k),"--output",str(out)]

OUT.mkdir(parents=True,exist_ok=True)
summary=[]
for alg in ALGORITHMS:
    for name,data,meta,w,s,_minsup,windows in DATASETS:
        final=OUT/alg/f"{name}.json"
        if final.exists():
            r=json.loads(final.read_text()); summary.append(r); print("SKIP",alg,name,r["status"],flush=True); continue
        if alg in {"OPS-Miner","OPS-NoReuse"}:
            src=PRIOR/f"{alg}-{name}.json"; q=json.loads(src.read_text())
            r={"algorithm":alg,"dataset":name,"status":"measured","elapsed_seconds":q["elapsed_seconds"],"peak_rss_mib":q["peak_rss_mib"],"patterns_total":q["patterns_total"],"patterns_mean_per_window":q["patterns_mean_per_window"],"windows":windows}
            save(final,r); summary.append(r); print("REUSE",alg,name,r["elapsed_seconds"],flush=True); continue
        first=OUT/alg/f"{name}-first-window.json"
        if not first.exists():
            print("FIRST",alg,name,flush=True)
            subprocess.run(cmd(alg,data,meta,w,s,1,first),cwd=ROOT,check=True,capture_output=True,text=True,timeout=200)
        q=json.loads(first.read_text()); estimate=q["elapsed_seconds"]*windows
        if estimate>200:
            r={"algorithm":alg,"dataset":name,"status":"estimated","estimated_seconds":estimate,"first_window_seconds":q["elapsed_seconds"],"first_window_peak_rss_mib":q["peak_rss_mib"],"first_window_patterns":q["patterns_total"],"windows":windows}
            save(final,r); summary.append(r); print("ESTIMATE",alg,name,estimate,flush=True); continue
        pending=OUT/alg/f"{name}.pending.json"; print("FULL",alg,name,"projected",estimate,flush=True)
        started=time.perf_counter()
        try:
            subprocess.run(cmd(alg,data,meta,w,s,windows,pending),cwd=ROOT,check=True,capture_output=True,text=True,timeout=200)
        except subprocess.TimeoutExpired:
            r={"algorithm":alg,"dataset":name,"status":"estimated_after_timeout","estimated_seconds":estimate,"first_window_seconds":q["elapsed_seconds"],"stopped_after_seconds":time.perf_counter()-started,"windows":windows}
        else:
            z=json.loads(pending.read_text()); r={"algorithm":alg,"dataset":name,"status":"measured","elapsed_seconds":z["elapsed_seconds"],"peak_rss_mib":z["peak_rss_mib"],"patterns_total":z["patterns_total"],"patterns_mean_per_window":z["patterns_mean_per_window"],"first_window_seconds":q["elapsed_seconds"],"windows":windows}
        save(final,r); summary.append(r); print("DONE",alg,name,r["status"],r.get("elapsed_seconds",r.get("estimated_seconds")),flush=True)
save(OUT/"summary.json",summary)
print("ALL_DONE",flush=True)
