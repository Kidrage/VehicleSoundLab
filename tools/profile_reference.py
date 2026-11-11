"""Create local reference spectrograms and candidate-window measurements."""
import sys
import argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'python_deps'))
import json
import hashlib
import numpy as np
import scipy.signal as sig
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'references/analysis'

def coverage(x,sr):
    n=8192; hop=1024; counts=(4,8,16,32,64)
    win=np.hanning(n); scores={str(k):[] for k in counts}; high_scores={str(k):[] for k in counts}
    for start in range(0,len(x)-n,hop):
        p=np.abs(np.fft.rfft(x[start:start+n]*win))**2
        f=np.fft.rfftfreq(n,1/sr); valid=(f>=80)&(f<=16000)
        peaks=sig.find_peaks(p)[0]; peaks=peaks[valid[peaks]]
        peaks=peaks[np.argsort(p[peaks])[::-1]]
        total=max(p[valid].sum(),1e-20)
        for k in counts:
            mask=np.zeros(len(p),bool)
            for peak in peaks[:k]:mask[max(0,peak-2):peak+3]=True
            scores[str(k)].append(float(p[mask&valid].sum()/total))
            high=(f>=1200)&(f<=16000)
            high_scores[str(k)].append(float(p[mask&high].sum()/max(p[high].sum(),1e-20)))
    return {k:dict(median=float(np.median(v)),p10=float(np.percentile(v,10)),p90=float(np.percentile(v,90)),
        high_band_1200_16000_median=float(np.median(high_scores[k]))) for k,v in scores.items()}

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--id',choices=['A','B'],default='A');args=parser.parse_args()
    identity=args.id
    OUT.mkdir(parents=True,exist_ok=True)
    source=ROOT/f'references/clean/{identity}_decoded_float.wav'
    x,sr=sf.read(source,dtype='float32',always_2d=True)
    mono=x.mean(axis=1); dec=sig.resample_poly(mono,1,4); low_sr=sr/4
    f,t,p=sig.spectrogram(dec,low_sr,nperseg=2048,noverlap=1792,mode='psd')
    db=10*np.log10(p+1e-18)
    fig,axes=plt.subplots(4,1,figsize=(16,11),constrained_layout=True)
    sections=((0,90),(90,180),(180,270),(270,374)) if identity=='A' else ((0,210),(210,420),(420,630),(630,852))
    for ax,(start,end) in zip(axes,sections):
        select=(t>=start)&(t<end)
        im=ax.pcolormesh(t[select],f,db[:,select],shading='auto',vmin=-95,vmax=-30,cmap='magma',rasterized=True)
        ax.set_ylim(60,6000);ax.set_ylabel('Hz');ax.set_xlabel('Source time (s)')
        for pos,name in (((33,'Strada'),(164,'Sport'),(206,'Corsa')) if identity=='A' else ()):
            if start<pos<end:ax.axvline(pos,color='cyan',alpha=.7);ax.text(pos+1,5500,name,color='cyan')
    fig.suptitle(f'Reference {identity} / '+('Huracan Performante' if identity=='A' else 'Huracan Tecnica (user-supplied MP3)')+' / unprocessed float decode\nCamera context catalogued separately; absolute RPM not verified')
    fig.colorbar(im,ax=axes,shrink=.8,label='PSD (dB/Hz)')
    fig.savefig(OUT/f'{identity}_spectrogram.png',dpi=140);plt.close(fig)
    windows=[]
    for start in range(0,int(len(x)/sr)-4,2):
        a=mono[start*sr:(start+2)*sr]
        freq,psd=sig.welch(a,sr,nperseg=8192)
        region=(freq>=100)&(freq<=10000); total=max(float(psd[region].sum()),1e-20)
        peaks=sig.find_peaks(psd)[0];peaks=peaks[(freq[peaks]>=80)&(freq[peaks]<=6000)]
        peaks=peaks[np.argsort(psd[peaks])[::-1]][:10]
        rms=float(20*np.log10(max(float(np.sqrt(np.mean(a*a))),1e-12)))
        windows.append(dict(start=start,end=start+2,rms_dbfs=rms,
            centroid_hz=float(np.sum(freq[region]*psd[region])/total),
            flatness=float(np.exp(np.mean(np.log(psd[region]+1e-20)))/max(float(psd[region].mean()),1e-20)),
            peaks_hz=np.round(freq[peaks],2).tolist()))
    report=dict(source=str(source),sample_rate=sr,decoded_seconds=len(x)/sr,
        channels=x.shape[1],peak_dbfs=float(20*np.log10(np.max(np.abs(x)))),
        near_full_scale_fraction=float(np.mean(np.abs(x)>=.999)),
        channel_correlation=float(np.corrcoef(x.T)[0,1]),
        windows=windows,
        quality_notes=(['One terminal Opus packet produced a decoder warning; final tail is excluded from all selected clips.'] if identity=='A' else ['User-supplied MP3; original binaural phase and compression chain cannot be independently verified.'])+[
          'Float codec overshoots/near-full-scale values do not prove ADC or source clipping.',
          'Spectral peaks alone cannot verify original RPM, exhaust modifications, speech/music absence, or microphone position.'])
    (OUT/f'{identity}_window_catalog.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    usable=[w for w in windows if w['start']>=34 and w['end']<len(x)/sr-12 and w['rms_dbfs']>-32]
    print('SOURCE', {k:v for k,v in report.items() if k!='windows'})
    print('TONAL CANDIDATES',json.dumps(sorted(usable,key=lambda w:w['flatness'])[:10],indent=2))
    print('BRIGHT CANDIDATES',json.dumps(sorted(usable,key=lambda w:-w['centroid_hz'])[:10],indent=2))

if __name__=='__main__':main()
