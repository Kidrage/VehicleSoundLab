"""Separate carrier pitch, complex AM/PM, and finite interpolation effects.

The radial-only output is a causal ablation, not a replacement voice.
"""
from runtime_review import ROOT,sha
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import soundfile as sf
from scipy import signal

OUT=ROOT/'references/analysis/detail_modulation_v1'
BUILD=ROOT/'build-detail-modulation-audit-v1/Release'
MODEL=ROOT/'references/analysis/sustain_osc_v1/voice.model'
ORDERS=[5,10,15,20,25,30,40,50,60]


def statistics(z):
    magnitude=abs(z);valid=(magnitude[:-1]>.1*np.median(magnitude))&(magnitude[1:]>.1*np.median(magnitude))
    df=np.angle(z[1:]*z[:-1].conj())*1000/(2*np.pi)
    return dict(median_amplitude=float(np.median(magnitude)),near_zero_fraction=float(np.mean(magnitude<.1*np.median(magnitude))),
        coefficient_phase_step_equivalent_hz_RMS=float(np.sqrt(np.mean(df[valid]**2))),
        coefficient_phase_step_equivalent_hz_abs95=float(np.percentile(abs(df[valid]),95)),
        metric_limit='Coefficient-phase motion only, excluding amplitudes below10% median; not perceived pitch, physical RPM, or reliable instantaneous frequency near zeros.')


def observations():
    x,rate=sf.read(ROOT/'references/analysis/sustain_osc_v1/normalized_reference_float.wav',always_2d=True)
    starts=np.arange(0,len(x)-1024+1,256);k=np.arange(1,301)
    z=np.array([np.fft.rfft(x[s:s+1024],axis=0)[k]*2/1024*np.exp(-2j*np.pi*k*s/1024)[:,None] for s in starts])
    return z,rate/256


def main():
    OUT.mkdir(exist_ok=False)
    assert sha(MODEL)=='6f8992e6674f603334f82bdbc526fd8ac5bbe750606154c5e83c166c077bb1b7'
    def render(pair):
        name,amount=pair
        run=subprocess.run([str(BUILD/'detail_modulation_probe.exe'),str(MODEL),str(OUT/name),str(amount)],
            check=True,capture_output=True,text=True,timeout=60)
        return name,amount,run.stdout
    variants={};audio={};traces={};phases=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for name,amount,log in pool.map(render,[('detail000',0),('detail025',.25),('detail050',.5),('detail075',.75),('detail100',1)]):
            evidence=json.loads((OUT/f'{name}_probe.json').read_text())
            assert evidence['clock_error_vs_amount1']==0 and evidence['rng_and_updates_identical']
            assert evidence['coefficient_reconstruction_error']<1e-10
            t=np.genfromtxt(OUT/f'{name}_trace.csv',delimiter=',',names=True)
            assert (t['pitch']==1).all() and abs(t['amount']-amount).max()<1e-12
            phases.append(t['carrier_phase']);traces[name]=t
            x,r=sf.read(OUT/f'{name}_full_float.wav',always_2d=True)
            y,s=sf.read(OUT/f'{name}_radial_float.wav',always_2d=True)
            assert r==s==48000 and x.shape==y.shape==(768000,2) and np.isfinite(x).all() and np.isfinite(y).all()
            audio[name]=x;audio[name+'_radial']=y
            evidence.update(per_harmonic_L={str(h):statistics(t[f'h{h}_0']+1j*t[f'h{h}_1']) for h in ORDERS},
                raw_sha256=sha(OUT/f'{name}_full_float.wav'),radial_sha256=sha(OUT/f'{name}_radial_float.wav'))
            variants[name]=evidence
    assert all(np.array_equal(phases[0],p) for p in phases[1:])
    accepted,rate=sf.read(ROOT/'references/analysis/sustain_osc_v1/renders/generated_float.wav',always_2d=True)
    assert np.array_equal(audio['detail100'][:len(accepted)],accepted)
    assert np.array_equal(audio['detail000'],audio['detail000_radial']) or abs(audio['detail000']-audio['detail000_radial']).max()<1e-7
    #Fixed-phase coefficients preserve each channel's magnitude; check analytic construction with trace snapshots.
    model=dict(np.load(ROOT/'references/analysis/sustain_osc_v1/profile_arrays.npz'))
    magnitude_error=0;radial_phase_motion=0
    t=traces['detail050']
    for h in ORDERS:
        z=t[f'h{h}_0']+1j*t[f'h{h}_1'];mean=model['mean'][h-1,0]+1j*model['mean'][h-1,1]
        fixed=abs(z)*mean/abs(mean)
        magnitude_error=max(magnitude_error,float(abs(abs(fixed)-abs(z)).max()))
        radial_phase_motion=max(radial_phase_motion,statistics(fixed)['coefficient_phase_step_equivalent_hz_RMS'])
    assert magnitude_error<1e-14 and radial_phase_motion<1e-10
    #Same gain and exactly8s; not independent RMS/loudness matching.
    clips={};gain=.5
    for name in ['detail100','detail075','detail050','detail025','detail000','detail050_radial']:
        x=audio[name][:384000]*gain
        ramp=np.linspace(0,1,240);x[:240]*=ramp[:,None];x[-240:]*=ramp[::-1,None]
        assert abs(x).max()<.95
        path=OUT/f'{name}_audition.wav';sf.write(path,x,48000,subtype='PCM_24')
        clips[name]=dict(path=path.name,frames=len(x),gain=gain,sha256=sha(path),rms_dbfs=float(10*np.log10(np.mean(x*x))))
    assert sf.info(OUT/'detail100_audition.wav').frames==384000
    ref_a,rate=sf.read(ROOT/'references/analysis/sustain_osc_v1/renders/generated_audition.wav',always_2d=True)
    test_a,rate=sf.read(OUT/'detail100_audition.wav',always_2d=True)
    assert np.array_equal(ref_a,test_a)
    #Mean-source carrier lines vs sideband energy are diagnostic, not naturalness scores.
    sidebands={}
    for name in ['detail000','detail025','detail050','detail075','detail100','detail050_radial']:
        x=audio[name][:,0];f,p=signal.welch(x,48000,nperseg=65536)
        near=np.abs(f/46.875-np.round(f/46.875))*46.875<2
        selected=(f>=150)&(f<8000)
        sidebands[name]=float(10*np.log10(max(p[selected&~near].sum(),1e-30)/max(p[selected&near].sum(),1e-30)))
    result=dict(result='pass',model_sha256=sha(MODEL),variants=variants,auditions=clips,
        source_carrier_phase_identical_at_all_detail_values=True,
        nominal_pitch_and_modulation_clock_and_rng_unchanged=True,
        default16s_first8s_exact_accepted_source=True,default_PCM24_exact_accepted_audition=True,
        radial_ablation=dict(magnitude_preservation_error=magnitude_error,coefficient_phase_motion_rms=radial_phase_motion,
            limitation='Removes all per-channel temporal coefficient phase; changes spatial phase variations too. Diagnostic only; may flatten naturalness. Not integrated.'),
        band_sideband_to_line_ratio_db=sidebands,
        interpretation='Detail scales Cartesian complex fluctuations, so it includes AM and PM. Fixed detail still generates correlated random phase motion; no carrier pitch-routing bug found. Exact subjective cause and radial-only preference require listening.',
        interpolation_limit='Piecewise linear stochastic coefficients have update-phase-dependent variance; not ruled out as an additional contributor. No periodic pitch LFO or carrier reset is programmed.',
        binaries={'detail_modulation_probe.exe':sha(BUILD/'detail_modulation_probe.exe')},
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'experiments/detail_modulation_audit_v1').iterdir() if p.is_file()},
        accepted_native_changed=False,goal_complete=False)
    (OUT/'analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(result='pass',default_exact=True,carrier_clock_unchanged=True,
        order20={name:v['per_harmonic_L']['20'] for name,v in variants.items()},sidebands=sidebands),indent=2),flush=True)


if __name__=='__main__':main()
