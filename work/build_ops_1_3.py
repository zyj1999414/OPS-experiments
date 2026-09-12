#!/usr/bin/env python3
import csv, json, tarfile, tempfile, urllib.request, zipfile
from pathlib import Path
import numpy as np
import soundfile as sf
import pyedflib

ROOT=Path(__file__).resolve().parents[1]/'OPS-data'
CACHE=Path(__file__).resolve().parent/'ops-data-downloads'
M=1024*1024

def dl(url, path):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists(): return
    print('DOWNLOAD',url,flush=True)
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 Newsup research dataset builder'})
    with urllib.request.urlopen(req,timeout=180) as r, path.open('wb') as f:
        while True:
            b=r.read(4*M)
            if not b: break
            f.write(b)

class Writer:
    def __init__(self, folder, mib, meta):
        self.dir=ROOT/folder; self.dir.mkdir(parents=True,exist_ok=True)
        self.path=self.dir/f'{folder}_{mib}MiB.f64'
        self.f=self.path.open('wb'); self.need=mib*M//8; self.n=0; self.meta=meta
    def add(self,a):
        a=np.asarray(a,dtype='<f8').reshape(-1); k=min(len(a),self.need-self.n)
        if k: self.f.write(a[:k].tobytes()); self.n+=k
        return self.n>=self.need
    def done(self):
        self.f.close(); self.meta.update({'values':self.n,'bytes':self.path.stat().st_size,'format':'headerless little-endian float64'})
        (self.dir/'metadata.json').write_text(json.dumps(self.meta,ensure_ascii=False,indent=2)+'\n')
        print('DONE',self.path,self.path.stat().st_size,flush=True)

def finance():
    z=CACHE/'BTCUSDT-trades-2024-01.zip'; url='https://data.binance.vision/data/spot/monthly/trades/BTCUSDT/BTCUSDT-trades-2024-01.zip'; dl(url,z)
    w=Writer('01_finance_binance',64,{'source':url,'domain':'finance','variable':'BTCUSDT trade price'})
    with zipfile.ZipFile(z) as a, a.open(a.namelist()[0]) as f:
        buf=[]
        for row in csv.reader((x.decode() for x in f)):
            try: buf.append(float(row[1]))
            except: continue
            if len(buf)>=500000:
                if w.add(buf): break
                buf=[]
        if w.n<w.need: w.add(buf)
    w.done()

def speech():
    t=CACHE/'dev-clean.tar.gz'; url='https://www.openslr.org/resources/12/dev-clean.tar.gz'; dl(url,t)
    w=Writer('02_speech_librispeech',256,{'source':url,'domain':'speech','variable':'audio waveform amplitude','license':'CC BY 4.0'})
    with tempfile.TemporaryDirectory(dir=CACHE) as td:
        with tarfile.open(t,'r:gz') as a:
            for m in a:
                if not m.name.endswith('.flac'): continue
                f=a.extractfile(m)
                if not f: continue
                tmp=Path(td)/'x.flac'; tmp.write_bytes(f.read())
                data,_=sf.read(tmp,dtype='float64',always_2d=False)
                if w.add(data): break
    w.done()

def eeg():
    base='https://physionet.org/files/sleep-edfx/1.0.0/'
    records=CACHE/'sleep-edfx-RECORDS'; dl(base+'RECORDS',records)
    w=Writer('03_biomedical_sleep_edf',384,{'source':base,'domain':'biomedical EEG','variable':'EEG Fpz-Cz','license':'ODC-By 1.0'})
    for rel in records.read_text().splitlines():
        if not rel.endswith('PSG.edf'): continue
        p=CACHE/'sleep-edfx'/rel; dl(base+rel,p)
        e=pyedflib.EdfReader(str(p))
        try:
            labels=[x.strip() for x in e.getSignalLabels()]
            idx=next((i for i,x in enumerate(labels) if 'FPZ-CZ' in x.upper()),None)
            if idx is None: continue
            if w.add(e.readSignal(idx)): break
        finally: e.close()
    w.done()

if __name__=='__main__':
    finance(); speech(); eeg()
