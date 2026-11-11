"""Audible, independently versioned C response shapes on fresh native takes."""
import csv
import hashlib
import json
import subprocess
import time
from runtime_review import ROOT,sha,rms
from review_pairs import common_pair
import numpy as np
import soundfile as sf

OUT=ROOT/'renders/response_shape_v1'
PROBE=ROOT/'build-experiment-response-shape/Release/response_shape_probe.exe'
RECORDER=ROOT/'build-v017/Release/vsl_character_probe.exe'
NATIVE=ROOT/'build-v017/Release/vsl_take_render.exe'
VARIANTS={'fixed':0,'half':.5,'full':1}
LABELS={'fixed':'现有响应','half':'轻度变化','full':'完整变化'}
CASES={'low':('1200 RPM · 低转','fixed',5,1200,.18),'mid':('4000 RPM · 带载','fixed',5,4000,.85),
    'high':('8000 RPM · 带载','fixed',5,8000,.85),'neutral':('空挡补油与落转','neutral',8,850,.18),
    'lift':('5000 RPM · 收油与恢复','lift',7.5,5000,.85),'drive':('运动自动挡 · 30 秒','auto',30,850,.18)}


def run(args):
    start=time.perf_counter();r=subprocess.run(list(map(str,args)),cwd=ROOT,check=True,capture_output=True,text=True,timeout=90)
    return dict(stdout=r.stdout.strip(),elapsed_seconds=time.perf_counter()-start)


def audio(path):
    x,sr=sf.read(path,always_2d=True);assert sr==48000 and sf.info(path).subtype=='FLOAT'
    assert np.isfinite(x).all() and abs(x).max()<.95;return x


def rows(path):
    with path.open() as f:return list(csv.DictReader(f))


def main():
    if OUT.exists() and any(OUT.iterdir()):raise SystemExit('Preserve response_shape_v1; use a new experiment.')
    OUT.mkdir(parents=True);result=dict(experiment='response_shape_v1',base_runtime='0.17.0 unchanged',
        seed=48271,variants=VARIANTS,subjective_status='Unaccepted engineering audition. No native promotion.',cases={})
    pages={}
    for name,(label,scenario,seconds,rpm,load) in CASES.items():
        folder=OUT/name;folder.mkdir();take=folder/'input.vsltake'
        capture=run([RECORDER,take,scenario,seconds,rpm,load,.65,.65]);native=folder/'native.wav';run([NATIVE,take,native])
        arrays=[];variants={};trace=None;signature=None
        for tag,amount in VARIANTS.items():
            prefix=folder/tag;done=run([PROBE,take,prefix,amount,2]);x=audio(prefix.with_suffix('.wav'));arrays.append(x)
            assert len(x)==round(seconds*48000) and x.shape[1]==2
            meta=json.loads((folder/(tag+'_meta.json')).read_text())
            if tag=='fixed':assert prefix.with_suffix('.wav').read_bytes()==native.read_bytes()
            current=(folder/(tag+'.csv')).read_bytes()
            state=[{k:v for k,v in row.items() if k not in ['shape_min','shape_max']} for row in rows(folder/(tag+'_state.csv'))]
            if trace is None:trace=current;signature=state
            assert current==trace and state==signature
            variants[tag]=dict(**done,metadata=meta,sha256=sha(prefix.with_suffix('.wav')),rms_dbfs=rms(x),peak=float(abs(x).max()))
        stems={}
        for path in sorted(folder.glob('fixed_source_*.wav')):
            source=path.name[len('fixed_source_'):-4];identical=[]
            for tag in ['half','full']:
                after=folder/(tag+'_source_'+source+'.wav');same=path.read_bytes()==after.read_bytes()
                assert same or source in ['exhaust_left','exhaust_right','body','mechanical'],source
                if same:identical.append(tag)
            stems[source]=identical
        auditions=common_pair(folder,arrays,list(VARIANTS),name)
        pages[name]=dict(label=label,takes={tag:'../renders/response_shape_v1/'+name+'/'+auditions[tag]['file'] for tag in VARIANTS},gain_db=auditions['fixed']['gain_db'])
        difference={tag:dict(AC_difference_over_original_db=(10*np.log10(np.var(x-arrays[0],axis=0)/np.var(arrays[0],axis=0))).tolist())
            for tag,x in zip(list(VARIANTS)[1:],arrays[1:])}
        # Do not use a large null ratio to advertise realism; it only confirms
        # how much waveform is changed by this controlled parameterization.
        result['cases'][name]=dict(label=label,scenario=scenario,seconds=seconds,rpm_input=rpm,load_input=load,
            capture=capture,input_sha256=sha(take),variants=variants,auditions=auditions,
            identical_native_controls_events_and_driving=True,unchanged_stems=stems,difference=difference)
        if name=='high':
            done=run([PROBE,take,folder/'full_714',1,12])
            assert (folder/'full.csv').read_bytes()==(folder/'full_714.csv').read_bytes()
            assert (folder/'full_state.csv').read_bytes()==(folder/'full_714_state.csv').read_bytes()
            for source in stems:assert (folder/('full_source_'+source+'.wav')).read_bytes()==(folder/('full_714_source_'+source+'.wav')).read_bytes()
            result['bed714']=dict(identical_ten_source_stems=True,identical_native_and_response_states=True,
                actual_array_listening=False,render=done)
        print(json.dumps(dict(case=name,difference=difference,coordinate_range=[variants['full']['metadata']['coordinate_min'],variants['full']['metadata']['coordinate_max']])),flush=True)
    for kind,kind_id in [('pressure',0),('structure',1)]:
        for value in [-1,-.5,.5,1]:run([PROBE,'impulse',OUT/f'impulse_{kind}_{value:+.1f}.wav',value,kind_id])
    template=ROOT/'tools/response_shape_page.html';page=ROOT/'research/燃烧响应形状试听V1.html'
    text=template.read_text(encoding='utf-8').replace('__DATA__',json.dumps(pages,ensure_ascii=False).replace('</','<\\/'))
    text=text.replace('__METHODS__',json.dumps(LABELS,ensure_ascii=False));page.write_text(text,encoding='utf-8')
    upstream=ROOT/'research/upstream_v6_response/v10_powertrain.gendsp';blob=upstream.read_bytes()
    assert hashlib.sha1(b'blob '+str(len(blob)).encode()+b'\0'+blob).hexdigest()=='229ca56db010298e4eec684d459d586c62034c9e'
    result['upstream']=dict(repository='https://github.com/Kidrage/VehicleSoundSynth',checked_head='ac2b37d8639027d79934a2023cf8d1d37d3b2f96',
        path='gen/v10_powertrain.gendsp',git_blob_sha1='229ca56db010298e4eec684d459d586c62034c9e',sha256=sha(upstream),
        scope='Read-only text supplement. Shares layering/control method; constants here are not Lamborghini calibration.')
    names=[p.relative_to(ROOT).as_posix() for p in sorted((ROOT/'experiments/response_shape_v1').glob('*')) if p.is_file()]
    names+=['tools/render_response_shape.py','tools/response_shape_page.html','tools/seekable_review_player_v1.js','tools/review_pairs.py',
        page.relative_to(ROOT).as_posix(),upstream.relative_to(ROOT).as_posix(),
        'baselines/v0.17.0/manifest.json','baselines/v0.17.0/bin/vsl_core.lib',
        'build-experiment-response-shape/Release/response_shape_probe.exe',
        'build-experiment-response-shape/Release/response_shape_checks.exe']
    result['sources']={name:sha(ROOT/name) for name in names}
    result['files']={p.relative_to(OUT).as_posix():sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
    (OUT/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False,ensure_ascii=False),encoding='utf-8')


if __name__=='__main__':main()
