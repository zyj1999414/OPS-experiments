#!/usr/bin/env python3
import json, tarfile, urllib.request
from pathlib import Path
import h5py, numpy as np
from astropy.io import fits
ROOT=Path(__file__).resolve().parents[1]/'OPS-data';CACHE=Path(__file__).resolve().parent/'ops-data-downloads';M=1024*1024
def dl(url,p):
 p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():return
 print('DOWNLOAD',url,flush=True);req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 Newsup research'})
 with urllib.request.urlopen(req,timeout=180) as r,p.open('wb') as f:
  while b:=r.read(8*M):f.write(b)
class W:
 def __init__(self,d,mib,meta):
  self.d=ROOT/d;self.d.mkdir(parents=True,exist_ok=True);self.p=self.d/f'{d}_{mib}MiB.f64';self.f=self.p.open('wb');self.need=mib*M//8;self.n=0;self.meta=meta
 def add(self,a):
  a=np.asarray(a,dtype='<f8').reshape(-1);a=a[np.isfinite(a)];k=min(len(a),self.need-self.n)
  if k:self.f.write(a[:k].tobytes());self.n+=k
  return self.n>=self.need
 def done(self):
  self.f.close();self.meta.update(values=self.n,bytes=self.p.stat().st_size,format='headerless little-endian float64');(self.d/'metadata.json').write_text(json.dumps(self.meta,ensure_ascii=False,indent=2)+'\n');print('DONE',self.p,flush=True)
def astronomy():
 url='https://archive.stsci.edu/pub/kepler/lightcurves/tarfiles/Q5_public/public_Q5_short_1.tgz';p=CACHE/'public_Q5_short_1.tgz';dl(url,p)
 w=W('07_astronomy_kepler',896,{'source':url,'domain':'astronomy','variable':'Kepler PDCSAP_FLUX','selection':'QUALITY == 0 and finite'})
 with tarfile.open(p,'r:gz') as t:
  for m in t:
   if not m.isfile() or not m.name.endswith('.fits'):continue
   f=t.extractfile(m)
   if not f:continue
   with fits.open(f,memmap=False) as hd:
    tab=hd[1].data
    x=tab['PDCSAP_FLUX'];q=tab['SAP_QUALITY']
    if w.add(x[q==0]):break
 w.done()
def ligo():
 api='https://gwosc.org/archive/links/O3a_4KHZ_R1/H1/1238166018/1238252418/json/'
 with urllib.request.urlopen(api) as r:info=json.load(r)
 urls=[]
 for x in info['strain']:
  if x.get('format')=='hdf5' and x['url'] not in urls:urls.append(x['url'])
 w=W('08_physics_ligo_gwosc',1024,{'source_api':api,'domain':'gravitational-wave physics','variable':'H1 strain at 4096 Hz','dataset':'O3a_4KHZ_R1'})
 for i,url in enumerate(urls):
  p=CACHE/'gwosc'/Path(url).name;dl(url,p)
  with h5py.File(p,'r') as h:
   x=h['strain']['Strain'][:]
  if w.add(x):break
 if w.n<w.need:raise RuntimeError(f'GWOSC interval supplied only {w.n} finite values')
 w.done()
if __name__=='__main__':astronomy();ligo()
