"""Independent explicit-FFT audit of raw references and actual C timing curves."""
import argparse
import json
from pathlib import Path
import numpy as np
import soundfile as sf
from event_designer.package import write_json

EDGES=((0,60),(60,300),(300,1200),(1200,4500),(4500,14000),(14000,24001))


def powers(x):
    if x.ndim==1:x=x[:,None]
    w=.5-.5*np.cos(2*np.pi*np.arange(2048)/2048)
    starts=np.arange(0,len(x)-2048+1,240);f=np.arange(1025)*48000/2048
    rows=[]
    for start in starts:
        z=np.fft.rfft(x[start:start+2048]*w[:,None],axis=0)
        p=(z.real*z.real+z.imag*z.imag)/(48000*np.sum(w*w));p[1:-1]*=2
        rows.append([np.mean(np.sum(p[(f>=lo)&(f<hi)],axis=0))*48000/2048 for lo,hi in EDGES])
    return (starts+1024)/48000,np.array(rows).T


def stats(t,rows):
    result=[]
    for row in rows:
        c=np.cumsum(row);indices=[min(len(t)-1,int(np.searchsorted(c,c[-1]*q))) for q in (.1,.5,.9)]
        result.append(dict(peak_seconds=float(t[np.argmax(row)]),energy_t10_t50_t90=[float(t[i]) for i in indices],
            early_quarter_fraction=float(row[t<.2].sum()/row.sum()),mean_power=float(row.mean())))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    out=p.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    root=Path('E:/VehicleSoundLab/references/analysis/startup_shape_v1')
    report=json.loads((root/'candidate2/report.json').read_text(encoding='utf-8'))
    master,rate=sf.read('E:/VehicleSoundLab/references/clean/A_decoded_float.wav',always_2d=True);assert rate==48000
    raw=master[1786560:1824960];bg=master[1680000:1737600]
    copied,_=sf.read(root/'candidate2/analysis/reference.wav',always_2d=True);assert np.array_equal(raw,copied)
    t,signal=powers(raw);_,noise=powers(bg);target=np.maximum(signal-noise.mean(axis=1)[:,None],0)
    source=stats(t,target)
    def close(actual,expected):
        for a,b in zip(actual,expected):
            for key in a:np.testing.assert_allclose(a[key],b[key],rtol=2e-12,atol=2e-14)
    close(source,report['original_source_bands'])
    old,_=sf.read(root/'diagnosis2/original-C.wav');_,original=powers(old[:len(raw)])
    close(stats(t,original),report['old_C_bands'])
    diagnostics=[]
    for item in report['generated']:
        seed=item['seed'];x,_=sf.read(root/f'candidate2/{seed}/synthesis.wav')
        _,power=powers(x[:len(raw)]);actual=stats(t,power);close(actual,item['bands'])
        assert np.all(x[len(raw):]==0)
        def error(y,target):
            a=np.cumsum(y)/y.sum();b=np.cumsum(target)/target.sum()
            return float(np.sqrt(np.mean((a-b)**2)))
        rows=[dict(hz=list(edges),original_cdf_rmse=error(a,s),candidate_cdf_rmse=error(b,s),
            source_early_fraction=source[k]['early_quarter_fraction'],candidate_early_fraction=actual[k]['early_quarter_fraction'])
            for k,(edges,a,b,s) in enumerate(zip(EDGES,original,power,target))]
        diagnostics.append(dict(seed=seed,bands=rows))
    write_json(out/'report.json',dict(result='passed',method='explicit 2048-frame periodic Hann, per-channel rFFT squared, one-sided PSD and band integration; independent of scipy.spectrogram and fitter',
        raw_reference_exact=True,all_four_C_seed_curves_and_summaries_verified=True,source_bands=source,
        actual_C_temporal_errors=diagnostics,all_tails_zero=True,
        limitation='The finite smooth envelope does not reproduce high-band multiple bursts; temporal metrics are not listening acceptance or physical source separation.'))
    print(json.dumps(dict(result='passed',seeds=len(diagnostics),midband=[r['bands'][2] for r in diagnostics])),flush=True)


if __name__=='__main__':main()
