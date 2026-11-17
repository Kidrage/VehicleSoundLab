"""Compare approved A startup spectral envelopes with the actual current C event."""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from event_authoring.audio import read,sha
from event_authoring.native import Renderer
from event_designer.package import write_json

EDGES=((0,60),(60,300),(300,1200),(1200,4500),(4500,14000),(14000,24001))


def curves(x):
    x=np.asarray(x,dtype=float)
    if x.ndim==1:x=x[:,None]
    f,t,p=signal.spectrogram(x,48000,window='hann',nperseg=2048,noverlap=1808,axis=0,
                            detrend=False,scaling='density',mode='psd')
    return t,np.array([p[(f>=lo)&(f<hi)].sum(axis=0).mean(axis=0)*(f[1]-f[0]) for lo,hi in EDGES])


def describe(t,p):
    result=[]
    for y in p:
        cumulative=np.cumsum(y)
        q=[float(t[min(len(t)-1,np.searchsorted(cumulative,a*cumulative[-1]))]) for a in (.1,.5,.9)]
        result.append(dict(peak_seconds=float(t[np.argmax(y)]),energy_t10_t50_t90=q,
                           early_quarter_fraction=float(y[t<.2].sum()/y.sum()),mean_power=float(y.mean())))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    preset=Path('E:/VehicleSoundLab/references/analysis/startup_handoff_v1/fixed1/startup.recipe.json')
    document=json.loads(preset.read_text(encoding='utf-8'))['event_overrides']['catch']
    master=Path('E:/VehicleSoundLab/references/clean/A_decoded_float.wav')
    x,rate,reference=read(master,37.22,38.02);background,_,bg=read(master,35.,36.2)
    renderer=Renderer(repo)
    y,rendered=renderer.render(document['parameters'],'catch',dict(seconds=1.2))
    sf.write(out/'original-C.wav',y,rate,subtype='FLOAT');sf.write(out/'original-reference.wav',x,rate,subtype='FLOAT')
    t,raw=curves(x);_,noise=curves(background);_,generated=curves(y[:len(x)])
    target=np.maximum(raw-noise.mean(axis=1)[:,None],0)
    source_stats=describe(t,target);generated_stats=describe(t,generated)
    figure,axes=plt.subplots(3,2,figsize=(11,9),constrained_layout=True)
    for k,ax in enumerate(axes.flat):
        ax.plot(t,target[k],label='Original acoustic excess');ax.plot(t,generated[k],label='Existing C')
        ax.set(title=f'{EDGES[k][0]}–{min(EDGES[k][1],24000)} Hz',xlabel='Seconds from fixed crop',ylabel='Band power FS²');ax.legend(fontsize=8);ax.grid(alpha=.2)
    figure.savefig(out/'envelopes.png',dpi=140);plt.close(figure)
    write_json(out/'report.json',dict(schema='vsl.startup-shape-observation/1',reference=reference,background=bg,
        source_preset_path=str(preset),source_preset_sha256=sha(preset),profile=document,
        source_bands=source_stats,generated_bands=generated_stats,band_edges=EDGES,render=rendered,
        observation='2048-frame Hann PSD,240-frame hop; mean channel powers; fixed-background PSD subtraction clamped at zero; no physical source separation or measured RPM.',
        timbre_accepted=False))
    shutil.copy2(__file__,out/'executed_inspection.py')
    print(json.dumps(dict(source=source_stats,generated=generated_stats)),flush=True)


if __name__=='__main__':main()
