"""Recompute all D fixed-probe powers from raw PCM using independent NumPy FFT."""
import argparse
import json
from pathlib import Path
import numpy as np
import soundfile as sf
from event_authoring.audio import sha
from research_archive_v1 import save,load


def psd(x):
    n=2048;window=.5-.5*np.cos(2*np.pi*np.arange(n)/n)
    cells=np.stack([x[first:first+n]*window[:,None] for first in range(0,len(x)-n+1,n//2)])
    fft=np.fft.rfft(cells,axis=1);power=np.abs(fft)**2/(48000*np.sum(window**2));power[:,1:-1]*=2
    return np.fft.rfftfreq(n,1/48000),power.mean(axis=(0,2))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=load(a.probe/'report.json');repo=Path(__file__).resolve().parents[1]
    plan=load(a.probe/'exact_sources/research/D_flame_probe_v1_plan.json')
    all_times=plan['visible_flame_frame_seconds']+plan['comparison_frame_seconds']
    assert [r['frame_seconds'] for r in result['rows']]==all_times
    source=Path(result['rows'][0]['probe']['source']['path']) if 'source' in result['rows'][0]['probe'] else Path('E:/VehicleSoundLab/references/clean/D_decoded_float.wav')
    assert sha(source)==plan['source_sha256']
    for name,expected in result['source_bindings'].items():
        assert sha(a.probe/'exact_sources'/name)==sha(repo/name)==expected,name
    def read(seconds):
        with sf.SoundFile(source) as file:
            first,last=[round(v*48000) for v in seconds];file.seek(first)
            return file.read(last-first,dtype='float64',always_2d=True)
    errors=[]
    for row in result['rows']:
        at=row['frame_seconds'];expected={k:[at+v for v in plan[field]] for k,field in
            [('event','event_offset_seconds'),('before','before_offset_seconds'),('after','after_offset_seconds')]}
        assert row['intervals']==expected
        parts={k:read(v) for k,v in expected.items()};powers={k:float(np.sum(x*x)/x.size) for k,x in parts.items()}
        for bg in ('before','after'):
            contrast=float(10*np.log10(powers['event']/powers[bg]));measured=next(b['full_contrast_db'] for b in row['probe']['backgrounds'] if b['name']==bg)
            assert abs(contrast-measured)<2e-12
        frequency,event=psd(parts['event'])
        for item in row['spectral_contrast']:
            _,background=psd(parts[item['background']])
            for band in item['bands']:
                lo,hi=band['hz'];mask=(frequency>=lo)&(frequency<hi if hi<24000 else frequency<=hi)
                for key,power in (('event_welch_power',event),('background_welch_power',background)):
                    actual=float(power[mask].sum()*48000/2048);target=band[key]
                    assert np.isclose(actual,target,rtol=2e-12,atol=1e-24),(at,key,band['hz'],actual,target)
                    errors.append(abs(actual-target))
        assert row['fixed_window_check']['both_full_band_above_3db'] is False
    assert not result['fit_performed'] and not result['physical_identity_confirmed']
    save(a.output,dict(result='passed',fixed_rows=12,both_backgrounds_verified=True,six_bands_independent_numpy_fft=True,
        maximum_absolute_power_error=max(errors),all_full_band_contrasts_below_both_3db=True,
        no_acoustic_identity_inferred=True,goal_complete=False))
    print(json.dumps(load(a.output)),flush=True)


if __name__=='__main__':main()
