#!/usr/bin/env python3
import json, shutil, tarfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
src=root/'work/ops-data-downloads/public_Q5_short_1.tgz'
out=root/'OPS-data/07_astronomy_kepler'
fitsdir=out/'fits_lightcurves';fitsdir.mkdir(parents=True,exist_ok=True)
target=896*1024*1024; total=0; count=0
with tarfile.open(src,'r|gz') as t:
 for m in t:
  if not m.isfile() or not m.name.endswith('.fits'):continue
  f=t.extractfile(m)
  if not f:continue
  p=fitsdir/Path(m.name).name
  with p.open('wb') as g:shutil.copyfileobj(f,g,4*1024*1024)
  total+=p.stat().st_size;count+=1
  if total>=target:break
meta={'source':'https://archive.stsci.edu/pub/kepler/lightcurves/tarfiles/Q5_public/public_Q5_short_1.tgz','domain':'astronomy','representation':'native Kepler short-cadence FITS light curves','files':count,'bytes':total,'target_mib':896}
(out/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
print('DONE',count,total,flush=True)
