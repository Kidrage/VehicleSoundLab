"""Inspect new stationary B intervals before selecting any acoustic root."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import read,sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_explore.py')
r=dict(schema='vsl.B-stationary-exploration/1',source_sha256=sha(Path(__file__)),cases=[],model_exported=False)
fig,axes=plt.subplots(4,1,figsize=(13,11),constrained_layout=True)
for j,(segment,lo,hi) in enumerate([
    ('B_stationary_departure_context',132,134),('B_stationary_departure_context',134,136),
    ('B_arrival_parking_context',800,802),('B_arrival_parking_context',803,805)]):
    audio,provenance=read(a.workspace,segment,'interior_dynamic_observation')
    start=provenance['seconds'][0]
    x=audio[round((lo-start)*48000):round((hi-start)*48000)]
    hz,psd=signal.welch(x,48000,nperseg=48000,noverlap=24000,nfft=65536,axis=0,detrend=False)
    power=psd.mean(axis=1);db=10*np.log10(np.maximum(power,1e-30))
    indices,properties=signal.find_peaks(db,prominence=6)
    take=(hz[indices]>=20)&(hz[indices]<1200)&(db[indices]>=db[(hz>=20)&(hz<1200)].max()-40)
    indices=indices[take];prominence=properties['prominences'][take]
    order=np.argsort(power[indices])[::-1][:30];indices=indices[order];prominence=prominence[order]
    rows=[]
    for k,prom in zip(indices,prominence):
        left,mid,right=db[k-1:k+2];offset=.5*(left-right)/(left-2*mid+right)
        f=float(hz[k]+np.clip(offset,-.5,.5)*(hz[1]-hz[0]))
        rows.append(dict(hz=f,dbfs_per_hz=float(db[k]),relative_db=float(db[k]-db[indices[0]]),prominence_db=float(prom)))
    item=dict(seconds=[lo,hi],provenance=provenance,peaks=rows,
        rms_dbfs_LR=(10*np.log10(np.mean(x*x,axis=0))).tolist(),
        rule='1s Hann Welch/0.5s overlap; original stereo; measured peaks, no engine order or RPM labels')
    r['cases'].append(item)
    axes[j].plot(hz,db);axes[j].set(xlim=(20,1200),ylim=(db[(hz>=20)&(hz<1200)].max()-55,db.max()+2),
        title=f'B user MP3 {lo}..{hi}s | unchanged stereo mean power selection view',xlabel='Observed Hz',ylabel='dBFS/Hz')
    print(json.dumps(dict(seconds=item['seconds'],peaks=rows[:12])),flush=True)
fig.savefig(a.out/'spectra.png',dpi=140);plt.close(fig)
r['plot_sha256']=sha(a.out/'spectra.png')
(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
