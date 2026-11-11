"""Canonical exterior spectra and harmonic-spacing hypotheses, not RPM truth."""
import csv
import json
from pathlib import Path
from runtime_review import ROOT,sha
from reference_segments import read_segment
from harmonic_family import track,comb_scores
import numpy as np
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=ROOT/'references/analysis/order_families_v1'
CASES=[('low_rev','A_exterior_low_rev','order_candidates'),
    ('blips','A_exterior_blips','exterior_dynamic_observation'),
    ('moving','A_exterior_moving','exterior_dynamic_observation')]


def controls():
    rate=48000;t=np.arange(2*rate)/rate
    result={}
    for name,orders in [('full_family',range(1,17)),('even_only',range(2,17,2)),('single_tone',[2])]:
        audio=np.zeros((len(t),2))
        for n in orders:
            for c in range(2):audio[:,c]+=.07/n**.7*np.cos(2*np.pi*52.3*n*t+.19*n+.3*c)
        _,_,_,rows=track(audio,rate)
        estimate=float(np.median([r['spacing_hz'] for r in rows]))
        result[name]=dict(known_base_hz=52.3,emitted_orders=list(orders),estimated_spacing_hz=estimate,
            central_candidates=rows[len(rows)//2]['candidates'])
    assert abs(result['full_family']['estimated_spacing_hz']-52.3)<.5
    assert abs(result['even_only']['estimated_spacing_hz']-104.6)<.5
    result['lesson']='Even-only and single-line controls cannot establish the original base: a comb selects emitted spacing, not physical firing frequency or RPM.'
    return result


def main():
    OUT.mkdir(parents=True,exist_ok=True);data={};fig,axes=plt.subplots(3,2,figsize=(14,11),constrained_layout=True)
    for (name,identity,use),ax in zip(CASES,axes):
        x,rate,provenance=read_segment(identity,use)
        hz,t,p,rows=track(x,rate)
        offset=provenance['source_seconds'][0]
        with (OUT/f'{name}_spacing.csv').open('w',newline='') as f:
            w=csv.writer(f);w.writerow(['source_seconds','top_spacing_hz','score_db',
                'second_spacing_hz','second_score_db','third_spacing_hz','third_score_db'])
            w.writerows([offset+r['seconds'],r['spacing_hz'],r['score_db'],
                r['candidates'][1]['spacing_hz'],r['candidates'][1]['score_db'],
                r['candidates'][2]['spacing_hz'],r['candidates'][2]['score_db']] for r in rows)
        select=(hz>=30)&(hz<=1800)
        ax[0].pcolormesh(t+offset,hz[select],10*np.log10(np.maximum(p.mean(axis=1)[select],1e-30)),
            shading='auto',vmin=-85,vmax=-20,cmap='magma')
        ax[0].set(title=f'{name}: mean channel PSD',xlabel='Source seconds',ylabel='Hz',ylim=(30,1800))
        for order in [1,2,3,4,6,8]:
            ax[0].plot([r['seconds']+offset for r in rows],[r['spacing_hz']*order for r in rows],
                color='cyan',alpha=.45,lw=.6)
        f,ps=signal.welch(x,rate,nperseg=48000,noverlap=24000,axis=0)
        mean=ps.mean(axis=1)
        for c,side in enumerate(['L','R']):ax[1].semilogx(f,10*np.log10(np.maximum(ps[:,c],1e-30)),lw=.7,label=side)
        ax[1].set(title=f'{name}: raw full-clip Welch; not order-aligned',xlabel='Hz',ylabel='dBFS/Hz',xlim=(30,12000),ylim=(-100,-10))
        ax[1].grid(alpha=.2);ax[1].legend()
        peaks=signal.find_peaks(mean)[0];peaks=peaks[(f[peaks]>=30)&(f[peaks]<=2000)]
        peaks=peaks[np.argsort(mean[peaks])[::-1]][:16]
        spacing=np.array([r['spacing_hz'] for r in rows])
        bands={}
        for lo,hi in [(30,150),(150,600),(600,1200),(1200,3000),(3000,8000),(8000,14000)]:
            power=ps[(f>=lo)&(f<hi)].sum(axis=0)*(f[1]-f[0])
            bands[f'{lo}_{hi}']=dict(power_dbfs_lr=(10*np.log10(np.maximum(power,1e-30))).tolist())
        data[name]=dict(provenance=provenance,spacing_p10_median_p90_hz=np.percentile(spacing,[10,50,90]).tolist(),
            largest_mean_power_peaks=[dict(hz=float(f[k]),dbfs_per_hz=float(10*np.log10(mean[k]))) for k in peaks],
            bands=bands,rows=rows,
            interpretation='Automatic top comb hypothesis per frame; abrupt octave/harmonic swaps are possible, especially during rapid revs. No video RPM validation.')
        print(name,'spacing p10/50/90',data[name]['spacing_p10_median_p90_hz'],flush=True)
    fig.savefig(OUT/'spectral_families.png',dpi=140);plt.close(fig)
    result=dict(schema='vsl.harmonic-family-observations/1',controls=controls(),recordings=data,
        analysis=dict(window_seconds=.5,hop_seconds=.05,fft_size=65536,
            resolution='2 Hz native bin spacing; 0.7324 Hz zero-padded grid is not resolving power.',
            scoring='Mean L/R power; 35 Hz local median subtraction; positive contrast soft-limited by 30*tanh(dB/30), sampled at harmonics up to order 24 / 1600 Hz, n^-0.25 mean.',
            source_processing='None; channels retained. Mean powers only for common peak selection.'),
        limits=['A spacing is not a crank frequency, an engine-bank separation or measured RPM.',
            'Harmonic omissions and source/microphone transfer cause octave/subharmonic alternatives.',
            'Half-second windows smear rapid revs and cannot label shifts, pedal or load.',
            'A single recorded perspective cannot identify separate engine spectra and acoustic transfer.',
            'No runtime voicing or RPM constants changed by this analysis.'],
        tools={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in [Path(__file__),ROOT/'tools/harmonic_family.py',ROOT/'tools/reference_segments.py']})
    (OUT/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result['controls'],indent=2))


if __name__=='__main__':main()
