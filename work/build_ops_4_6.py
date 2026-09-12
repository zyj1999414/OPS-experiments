#!/usr/bin/env python3
import csv, gzip, json, tarfile, urllib.request
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]/'OPS-data'; CACHE=Path(__file__).resolve().parent/'ops-data-downloads'; M=1024*1024
def dl(url,p):
 p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists(): return
 print('DOWNLOAD',url,flush=True); req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 Newsup research'})
 with urllib.request.urlopen(req,timeout=180) as r,p.open('wb') as f:
  while b:=r.read(8*M): f.write(b)
class W:
 def __init__(self,d,mib,meta):
  self.d=ROOT/d;self.d.mkdir(parents=True,exist_ok=True);self.p=self.d/f'{d}_{mib}MiB.f64';self.f=self.p.open('wb');self.need=mib*M//8;self.n=0;self.meta=meta
 def add(self,a):
  a=np.asarray(a,dtype='<f8').reshape(-1);k=min(len(a),self.need-self.n)
  if k:self.f.write(a[:k].tobytes());self.n+=k
  return self.n>=self.need
 def done(self):
  self.f.close();self.meta.update(values=self.n,bytes=self.p.stat().st_size,format='headerless little-endian float64');(self.d/'metadata.json').write_text(json.dumps(self.meta,ensure_ascii=False,indent=2)+'\n');print('DONE',self.p,flush=True)
def weather():
 url='https://www.ncei.noaa.gov/data/global-hourly/archive/csv/2024.tar.gz';p=CACHE/'noaa-isd-2024.tar.gz';dl(url,p)
 w=W('04_weather_noaa_isd',512,{'source':url,'domain':'weather','variable':'air temperature TMP in degrees C'})
 with tarfile.open(p,'r:gz') as t:
  for member in t:
   if not member.isfile() or not member.name.endswith('.csv'):continue
   f=t.extractfile(member)
   if not f:continue
   rows=csv.DictReader((x.decode('utf-8',errors='replace') for x in f));buf=[]
   for row in rows:
    raw=row.get('TMP','').split(',')[0]
    try:v=int(raw)/10
    except:continue
    if abs(v)>=999:continue
    buf.append(v)
   if w.add(buf):break
 w.done()
def transport():
 w=W('05_transport_nyc_tlc',640,{'source':'https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page','domain':'urban transportation','variable':'trip duration seconds','product':'High Volume FHV'})
 for month in range(1,13):
  url=f'https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_2024-{month:02d}.parquet';p=CACHE/f'fhvhv_2024-{month:02d}.parquet';dl(url,p)
  pf=pq.ParquetFile(p)
  for batch in pf.iter_batches(batch_size=1000000,columns=['pickup_datetime','dropoff_datetime']):
   a=batch.column(0).to_numpy(zero_copy_only=False);b=batch.column(1).to_numpy(zero_copy_only=False);x=(b-a)/np.timedelta64(1,'s');x=x[(x>=0)&(x<7*24*3600)]
   if w.add(x):break
  if w.n>=w.need:break
 w.done()
def webviews():
 base='https://dumps.wikimedia.org/other/pageviews/2024/2024-01';w=W('06_web_wikimedia_pageviews',768,{'source':base+'/','domain':'web usage','variable':'hourly pageview count'})
 for day in range(1,32):
  for hour in range(24):
   name=f'pageviews-202401{day:02d}-{hour:02d}0000.gz';url=f'{base}/{name}';p=CACHE/'wikimedia'/name;dl(url,p);buf=[]
   with gzip.open(p,'rt',encoding='utf-8',errors='replace') as f:
    for line in f:
     parts=line.rsplit(' ',2)
     if len(parts)!=3:continue
     try:buf.append(int(parts[1]))
     except:continue
     if len(buf)>=1000000:
      if w.add(buf):break
      buf=[]
   if w.n<w.need and buf:w.add(buf)
   if w.n>=w.need:break
  if w.n>=w.need:break
 w.done()
if __name__=='__main__':weather();transport();webviews()
