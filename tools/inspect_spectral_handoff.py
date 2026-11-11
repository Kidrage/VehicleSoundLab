"""Measure actual frozen V010 bank-order amplitudes around the OSC handoff."""
import json
from runtime_review import ROOT,render,sha
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=ROOT/'references/analysis/spectral_handoff_v1'
OLD=ROOT/'baselines/v0.10.0/bin/vsl_render.exe'
RPMS=[1200,2400,4000,6000,8000]


def amplitudes(path,rpm):
    x,sr=sf.read(path);x=x[round(2*sr):round(4*sr)]
    t=np.arange(len(x))/sr;window=np.hanning(len(x))
    orders=np.arange(1,61);hz=rpm/24*orders
    z=(x*window)@np.exp(-2j*np.pi*t[:,None]*hz[None,:])
    return (2*abs(z)/window.sum()).tolist()


def main():
    OUT.mkdir(parents=True,exist_ok=True);report={};fig,axes=plt.subplots(2,1,figsize=(11,9),constrained_layout=True)
    for load,ax in zip([.18,.85],axes):
        takes={}
        for rpm in RPMS:
            name=f'rpm{rpm}_load{int(load*100)}'
            _,info=render(OLD,OUT/f'{name}.wav',['--rpm',str(rpm),'--load',str(load),'--pure',
                '--irregularity','0','--seconds','4.2'],'0.10.0',['--stems',str(OUT/name)])
            amplitude=amplitudes(OUT/f'{name}_exhaust_left.wav',rpm)
            db=20*np.log10(np.maximum(amplitude,1e-20))
            ax.plot(np.arange(1,61),db,label=f'{rpm} RPM',marker='.',ms=2,lw=.8)
            takes[str(rpm)]=dict(render=info,bank_order_amplitudes=amplitude,
                order26_to25_db=float(db[25]-db[24]),order28_to25_db=float(db[27]-db[24]))
        ax.axvline(128/5,color='black',ls='--',alpha=.5,label='128-cycle-partial boundary')
        ax.set(title=f'Actual left exhaust source / Pure OSC, irregularity 0, load {load}',
            xlabel='Bank harmonic order (RPM / 24 spacing)',ylabel='Amplitude dBFS',xlim=(15,50),ylim=(-115,-30))
        ax.grid(alpha=.2);ax.legend(ncol=3,fontsize=8);report[str(load)]=takes
    fig.savefig(OUT/'handoff.png',dpi=140);plt.close(fig)
    result=dict(schema='vsl.spectral-handoff/1',version='0.10.0',cases=report,
        source_code=dict(dna=sha(ROOT/'baselines/v0.10.0/src/core/dna.c'),high_orders=sha(ROOT/'baselines/v0.10.0/src/core/high_orders.c')),
        analysis='Hann complex projection over 2-4 s of actual mono float source stem, n*RPM/24. Pure OSC, zero irregularity; no recording fitting or listener transfer.',
        limits='A discontinuity is a code-path observation, not proof of perceived defect or target-car envelope.')
    (OUT/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({load:{rpm:round(item['order26_to25_db'],2) for rpm,item in takes.items()} for load,takes in report.items()},indent=2))


if __name__=='__main__':main()
