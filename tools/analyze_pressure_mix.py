"""Counterfactual full mixes, actual native pressure events, unchanged driving."""
import json
import subprocess
from runtime_review import ROOT,sha
import numpy as np
import soundfile as sf
from scipy.fft import next_fast_len
from pressure_mix_response import recurrence,bandlimited,ratios

OUT=ROOT/'renders/pressure_mix_v1'
EXE=ROOT/'build-experiment-pressure-mix/Release/pressure_mix_probe.exe'
RECORDER=ROOT/'build-v017/Release/vsl_character_probe.exe'
CASES=[('low','fixed',4,1200,.65),('mid','fixed',4,4000,.65),('high','fixed',4,8000,.65),
       ('neutral','neutral',8,1200,.65),('lift','lift',7.5,5000,.85)]


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def run(args):
    result=subprocess.run(list(map(str,args)),check=True,capture_output=True,text=True,cwd=ROOT,timeout=90)
    print(result.stdout.strip(),flush=True)
    return result.stdout


def probe(take,prefix,mode,channels=2,replacement=None):
    return run([EXE,take,prefix,mode,channels,*([replacement] if replacement else [])])


def load(prefix,suffix=''):
    x,sr=sf.read(str(prefix)+suffix+'.wav',always_2d=True)
    assert sr==48000 and np.isfinite(x).all() and sf.info(str(prefix)+suffix+'.wav').subtype=='FLOAT'
    return x


def main():
    if OUT.exists() and any(OUT.iterdir()):raise SystemExit('Preserve pressure_mix_v1; use a new folder.')
    OUT.mkdir(parents=True);runs={}
    for name,scenario,seconds,rpm,load_value in CASES:
        folder=OUT/name;folder.mkdir();take=folder/'input.vsltake'
        run([RECORDER,take,scenario,seconds,rpm,load_value,.65,.65])
        native=folder/'native';observed=folder/'observed';replaced=folder/'replaced'
        probe(take,native,0);probe(take,observed,1)
        assert native.with_suffix('.wav').read_bytes()==observed.with_suffix('.wav').read_bytes()
        meta=read(folder/'observed_meta.json');n=meta['frames'];sr=meta['sample_rate']
        events=np.genfromtxt(folder/'observed_events.csv',delimiter=',',names=True)
        assert len(events)==meta['strikes']>0 and meta['resets']==0
        samples=np.fromfile(folder/'observed_samples.f64',dtype='<f8').reshape(n,3)
        assert np.isfinite(samples).all()
        exact=recurrence(events,meta,samples[:,2]);error=float(abs(exact-samples[:,:2]).max())
        assert error<2e-12,(name,error)
        period=int(next_fast_len(n+2*sr));period+=period%2
        pad_check,_=bandlimited(events,meta,samples[:,2],period,8)
        coarse,coarse_meta=bandlimited(events,meta,samples[:,2],2*period,8)
        final,final_meta=bandlimited(events,meta,samples[:,2],2*period,16)
        final.tofile(folder/'replacement.f64')
        sf.write(folder/'pressure_original.wav',samples[:,:2],sr,subtype='FLOAT')
        sf.write(folder/'pressure_bandlimited.wav',final,sr,subtype='FLOAT')
        probe(take,replaced,2,replacement=folder/'replacement.f64')
        # Replacing with exactly the captured contribution must be a true bypass.
        samples[:,:2].copy().tofile(folder/'bypass.f64')
        bypass=folder/'bypass';probe(take,bypass,2,replacement=folder/'bypass.f64')
        assert native.with_suffix('.wav').read_bytes()==bypass.with_suffix('.wav').read_bytes()
        for prefix in [observed,replaced,bypass]:
            for suffix in ['.csv','_state.csv']:
                assert (folder/('native'+suffix)).read_bytes()==(folder/(prefix.name+suffix)).read_bytes()
        for prefix in [replaced,bypass]:
            for suffix in ['_samples.f64','_events.csv']:
                assert (folder/('observed'+suffix)).read_bytes()==(folder/(prefix.name+suffix)).read_bytes()
        stems={}
        for path in sorted(folder.glob('native_source_*.wav')):
            stem=path.name[len('native_source_'):-4];replacement_path=folder/('replaced_source_'+stem+'.wav')
            unchanged=path.read_bytes()==replacement_path.read_bytes()
            assert unchanged or stem in ['exhaust_left','exhaust_right','body'],stem
            assert path.read_bytes()==(folder/('observed_source_'+stem+'.wav')).read_bytes()
            assert path.read_bytes()==(folder/('bypass_source_'+stem+'.wav')).read_bytes()
            stems[stem]=dict(unchanged=unchanged,original_sha256=sha(path),replacement_sha256=sha(replacement_path))
        a=load(native);b=load(replaced);pressure_score=ratios(final,samples[:,:2],sr)
        convergence=dict(grid_8_to_16=ratios(final,coarse,sr),period_1_to_2=ratios(final,pad_check,sr),
            grid_parameters=[coarse_meta,final_meta],
            limits='Measured convergence,not a rigorous infinite-padding error bound. Native post-gain can create new sidebands; this isolates ideal projection of the underlying pressure impulse only.')
        row=dict(scenario=scenario,seconds=seconds,rpm_input=rpm,load_input=load_value,
            pressure_control=.65,structure_control=.65,meta=meta,recurrence_max_error=error,
            full_mix=ratios(b,a,sr),pressure_only=pressure_score,convergence=convergence,stems=stems,
            baseline_bypass_and_state_contracts=True)
        if name=='high':
            for label,mode,replacement in [('native',0,None),('observed',1,None),('replaced',2,folder/'replacement.f64')]:
                prefix=folder/(label+'_714');probe(take,prefix,mode,12,replacement)
                assert (folder/(label+'_state.csv')).read_bytes()==(folder/(prefix.name+'_state.csv')).read_bytes()
                assert (folder/(label+'.csv')).read_bytes()==(folder/(prefix.name+'.csv')).read_bytes()
                for stem in stems:
                    assert (folder/(label+'_source_'+stem+'.wav')).read_bytes()==(folder/(prefix.name+'_source_'+stem+'.wav')).read_bytes()
            row['stereo_714_sources_and_states_identical']=True
        runs[name]=row
        print(json.dumps(dict(case=name,full_AC=row['full_mix']['bands']['AC']['difference_over_original_db'],
            pressure_AC=pressure_score['bands']['AC']['difference_over_original_db'],reconstruction_error=error)),flush=True)
    names=['tools/analyze_pressure_mix.py','tools/pressure_mix_response.py',
        'baselines/v0.17.0/manifest.json','baselines/v0.17.0/bin/vsl_core.lib',
        'build-experiment-pressure-mix/Release/pressure_mix_probe.exe','build-v017/Release/vsl_character_probe.exe']
    names+=list(p.relative_to(ROOT).as_posix() for p in sorted((ROOT/'experiments/pressure_mix_v1').glob('*')) if p.is_file())
    result=dict(study='pressure_mix_v1',base_runtime='0.17.0 unchanged',runs=runs,
        sources={name:sha(ROOT/name) for name in names},
        files={p.relative_to(OUT).as_posix():sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()},
        interpretation='Actual event-driven short pressure response counterfactual through native IR and scene. Not total full-engine aliasing or a measured/perceptual realism score. The replacement is offline and noncausal; native recipe is unchanged.')
    (OUT/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')


if __name__=='__main__':main()
