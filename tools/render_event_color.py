"""Audible main-pressure event coloration on fresh, strict native V018 takes."""
import csv
import json
import subprocess
import time
from runtime_review import ROOT, sha, rms
from reference_segments import read_segment
import numpy as np
import soundfile as sf

OUT=ROOT/'renders/event_color_v1'
PROBE=ROOT/'build-experiment-event-color/Release/event_color_probe.exe'
NATIVE=ROOT/'baselines/v0.18.0/bin'
VARIANTS={'fixed':0,'half':.5,'full':1}
CASES={'low':('1200 RPM · 低转','fixed',5,1200,.18,0,0,0),
       'mid':('4000 RPM · 带载','fixed',5,4000,.85,0,0,0),
       'high':('8000 RPM · 带载','fixed',5,8000,.85,0,0,0),
       'neutral':('空挡补油与落转','neutral',8,850,.18,0,0,0),
       'lift':('5000 RPM · 收油与恢复','lift',7.5,5000,.85,0,0,0),
       'drive':('运动自动挡 · 30 秒','auto',30,850,.18,0,0,0),
       'high_detail':('8000 RPM · 与现有细节合用','fixed',5,8000,.85,.65,.65,.75)}


def run(args):
    start=time.perf_counter()
    r=subprocess.run(list(map(str,args)),cwd=ROOT,check=True,capture_output=True,text=True,timeout=180)
    return dict(stdout=r.stdout.strip(),elapsed_seconds=time.perf_counter()-start)


def audio(path):
    x,sr=sf.read(path,always_2d=True)
    assert sr==48000 and sf.info(path).subtype=='FLOAT' and np.isfinite(x).all() and abs(x).max()<.95
    return x


def rows(path):
    with path.open(encoding='utf-8') as f:return list(csv.DictReader(f))


def audition(folder,arrays,name):
    gain=min(10**((-23-max(map(rms,arrays)))/20),.85/max(float(abs(x).max()) for x in arrays))
    meta={}
    for tag,x in zip(VARIANTS,arrays):
        fade=np.ones(len(x));ramp=.5-.5*np.cos(np.linspace(0,np.pi,240))
        fade[:240]=ramp;fade[-240:]=ramp[::-1]
        path=folder/f'audition_{name}_{tag}.wav';sf.write(path,x*gain*fade[:,None],48000,subtype='PCM_24')
        meta[tag]=dict(file=path.name,sha256=sha(path),gain_db=float(20*np.log10(gain)),
            raw_rms_dbfs=rms(x),endpoint_fade_ms=5,
            processing='Shared constant gain,5ms cosine endpoints,PCM24;no independent normalization,denoise,compression or HP.')
    return meta


def main():
    if OUT.exists() and any(OUT.iterdir()):raise SystemExit('Preserve prior event_color_v1 output; use a new experiment.')
    OUT.mkdir(parents=True)
    result=dict(experiment='event_color_v1',base_runtime='0.18.0 unchanged',seed=48271,cases={},
                subjective_status='Optional engineering candidate; no realism acceptance.')
    pages={}
    for name,(label,scenario,seconds,rpm,load,pressure,structure,shape) in CASES.items():
        folder=OUT/name;folder.mkdir();take=folder/'input.vsltake'
        capture=run([NATIVE/'vsl_character_probe.exe',take,scenario,seconds,rpm,load,pressure,structure,shape])
        native=folder/'native.wav';run([NATIVE/'vsl_take_render.exe',take,native])
        arrays=[];variants={};trace=None;state_signature=None
        for tag,amount in VARIANTS.items():
            prefix=folder/tag;args=[PROBE,take,prefix,amount,2]
            if name=='mid' and tag=='full':args.append('taps')
            done=run(args);x=audio(prefix.with_suffix('.wav'));arrays.append(x)
            assert x.shape==(round(seconds*48000),2)
            meta=json.loads((folder/f'{tag}_meta.json').read_text(encoding='utf-8'))
            if tag=='fixed':assert prefix.with_suffix('.wav').read_bytes()==native.read_bytes()
            current=(folder/f'{tag}.csv').read_bytes()
            signature=[tuple(r[k] for k in ['frame','native_state_fnv1a64','events_l','events_r']) for r in rows(folder/f'{tag}_state.csv')]
            if trace is None:trace=current;state_signature=signature
            assert current==trace and signature==state_signature
            assert meta['rejected_observed_events']==0 and meta['events_l']>0 and meta['events_r']>0
            variants[tag]=dict(**done,metadata=meta,sha256=sha(prefix.with_suffix('.wav')),rms_dbfs=rms(x),peak=float(abs(x).max()))
        stems={}
        for path in sorted(folder.glob('fixed_source_*.wav')):
            source=path.name[len('fixed_source_'):-4];identical=[]
            for tag in ['half','full']:
                after=folder/f'{tag}_source_{source}.wav';same=path.read_bytes()==after.read_bytes()
                assert same or source in ['exhaust_left','exhaust_right','body'],source
                if same:identical.append(tag)
            stems[source]=identical
        auditions=audition(folder,arrays,name)
        pages[name]=dict(label=label,takes={tag:f'../renders/event_color_v1/{name}/'+auditions[tag]['file'] for tag in VARIANTS},gain_db=auditions['fixed']['gain_db'])
        difference={tag:dict(difference_to_original_db=rms(x-arrays[0])-rms(arrays[0]),
                            change_in_RMS_db=rms(x)-rms(arrays[0])) for tag,x in zip(['half','full'],arrays[1:])}
        result['cases'][name]=dict(label=label,scenario=scenario,seconds=seconds,rpm_input=rpm,load_input=load,
            pressure_texture=pressure,structure_transfer=structure,response_shape=shape,capture=capture,input_sha256=sha(take),
            variants=variants,auditions=auditions,unchanged_stems=stems,difference=difference,
            identical_original_state_events_and_driving=True)
        if name=='high':
            done=run([PROBE,take,folder/'full_714',1,12])
            for suffix in ['.csv','_state.csv']:
                assert (folder/('full'+suffix)).read_bytes()==(folder/('full_714'+suffix)).read_bytes()
            for source in stems:
                assert (folder/f'full_source_{source}.wav').read_bytes()==(folder/f'full_714_source_{source}.wav').read_bytes()
            result['bed714']=dict(identical_ten_source_stems=True,identical_native_and_color_states=True,actual_array_listening=False,render=done)
        print(json.dumps(dict(case=name,difference=difference)),flush=True)
    references={}
    for name,use,label in [('A_exterior_low_rev','exterior_spectral_observation','A · 车外低转'),
                           ('A_exterior_blips','exterior_dynamic_observation','A · 车外补油')]:
        x,sr,provenance=read_segment(name,use);fade=np.ones(len(x));n=round(sr*.005)
        ramp=.5-.5*np.cos(np.linspace(0,np.pi,n));fade[:n]=ramp;fade[-n:]=ramp[::-1]
        path=OUT/f'reference_{name}.wav';sf.write(path,.5*x*fade[:,None],sr,subtype='PCM_24')
        references[name]=dict(label=label,file='../renders/event_color_v1/'+path.name,sha256=sha(path),provenance=provenance,
            gain_db=float(20*np.log10(.5)),endpoint_fade_ms=5,processing='Fixed0.5 gain,cosine5ms endpoints,PCM24. No other processing.')
    result['references']=references
    template=ROOT/'tools/event_color_page.html';page=ROOT/'research/主排气逐次形状试听V1.html'
    text=template.read_text(encoding='utf-8').replace('__DATA__',json.dumps(pages,ensure_ascii=False).replace('</','<\\/'))
    text=text.replace('__REFERENCES__',json.dumps(references,ensure_ascii=False).replace('</','<\\/'))
    page.write_text(text,encoding='utf-8')
    names=[p.relative_to(ROOT).as_posix() for p in sorted((ROOT/'experiments/event_color_v1').glob('*')) if p.is_file()]
    names+=['tools/render_event_color.py','tools/event_color_page.html','tools/seekable_review_player_v1.js',
            'tools/reference_segments.py','references/segments_v1.json',page.relative_to(ROOT).as_posix(),
            'baselines/v0.18.0/manifest.json','baselines/v0.18.0/bin/vsl_core.lib',
            'build-experiment-event-color/Release/event_color_probe.exe','build-experiment-event-color/Release/event_color_checks.exe']
    result['sources']={name:sha(ROOT/name) for name in names}
    result['files']={p.relative_to(OUT).as_posix():sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
    (OUT/'results.json').write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')


if __name__=='__main__':main()
