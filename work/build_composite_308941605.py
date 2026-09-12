from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
PARTS=[
 (ROOT/'OPS-data-main9/08_seismic_earthscope/08_seismic_earthscope_1GiB.f64',134_217_728),
 (ROOT/'OPS-data/08_physics_ligo_gwosc/08_physics_ligo_gwosc_1024MiB.f64',134_217_728),
 (ROOT/'OPS-data/05_transport_nyc_tlc/05_transport_nyc_tlc_640MiB.f64',40_506_149)]
TOTAL=sum(n for _,n in PARTS)
assert TOTAL==308_941_605
folder=ROOT/'OPS-data-main9/10_composite_scale_308941605'
folder.mkdir(parents=True,exist_ok=True)
temporary=folder/'composite_308941605.f64.partial'
target=folder/'composite_308941605.f64'
out=np.memmap(temporary,dtype='<f8',mode='w+',shape=(TOTAL,))
offset=0
chunk=4_000_000
for path,count in PARTS:
    source=np.memmap(path,dtype='<f8',mode='r',shape=(count,))
    for begin in range(0,count,chunk):
        end=min(begin+chunk,count)
        out[offset+begin:offset+end]=source[begin:end]
    offset+=count
    out.flush()
del out
assert temporary.stat().st_size==TOTAL*8
temporary.replace(target)
print(target)
print('points',target.stat().st_size//8)
print('bytes',target.stat().st_size)
print('MiB',target.stat().st_size/1048576)
