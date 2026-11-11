"""Versioned event-source audition; never modifies a native release or reference."""
import csv
import json
import subprocess
import time
from runtime_review import ROOT, sha, rms
import numpy as np
import soundfile as sf

OUT=ROOT/'renders/firing_pulse_v1'
PROBE=ROOT/'build-experiment-firing-pulse/Release/firing_pulse_probe.exe'
NATIVE=ROOT/'baselines/v0.19.0/bin'
VARIANTS={'original':0,'steady':1,'varying':2}
CASES={'mid':('4000 RPM', 'fixed',5,4000,.85,(2.5,5)),
       'high':('8000 RPM','fixed',5,8000,.85,(2.5,5)),
       'neutral':('空挡补油与落转','neutral',8,850,.18,(1.6,8)),
       'lift':('收油断油与恢复（验证）','lift',7.5,5000,.85,None)}

def run(args):
    start=time.perf_counter()
    r=subprocess.run(list(map(str,args)),cwd=ROOT,check=True,capture_output=True,text=True,timeout=180)
    return dict(stdout=r.stdout.strip(),seconds=time.perf_counter()-start)

def rows(path):
    with path.open(encoding='utf-8') as f:return list(csv.DictReader(f))

def main():
    if OUT.exists() and any(OUT.iterdir()):raise SystemExit('Preserve firing_pulse_v1; use a new output version.')
    OUT.mkdir(parents=True)
    result=dict(experiment='firing_pulse_v1',base_runtime='0.19.0',seed=48271,cases={},
                status='Engineering source-model audition, not accepted target calibration.')
    page={}
    for name,(label,scenario,seconds,rpm,load,crop) in CASES.items():
        folder=OUT/name;folder.mkdir();take=folder/'input.vsltake'
        capture=run([NATIVE/'vsl_character_probe.exe',take,scenario,seconds,rpm,load,0,0,0,0])
        run([NATIVE/'vsl_take_render.exe',take,folder/'native.wav'])
        arrays={};variants={};signature=None;trace=None;event_signature=None
        for tag,mode in VARIANTS.items():
            done=run([PROBE,take,folder/tag,mode,2])
            x,sr=sf.read(folder/f'{tag}.wav',always_2d=True)
            assert sr==48000 and x.shape==(round(seconds*sr),2) and np.isfinite(x).all() and abs(x).max()<.95
            if not mode:assert (folder/f'{tag}.wav').read_bytes()==(folder/'native.wav').read_bytes()
            arrays[tag]=x
            actual=rows(folder/f'{tag}_state.csv');current=[(r['frame'],r['native_source_state_fnv1a64']) for r in actual]
            log=(folder/f'{tag}.csv').read_bytes()
            if trace is None:trace=log;signature=current
            assert trace==log and signature==current
            events=[(r['events_l'],r['events_r']) for r in actual]
            if mode:
                if event_signature is None:event_signature=events
                assert event_signature==events
            meta=json.loads((folder/f'{tag}_meta.json').read_text(encoding='utf-8'))
            assert meta['overflow']==meta['denied']==0
            variants[tag]=dict(**done,metadata=meta,rms_dbfs=rms(x),peak=float(abs(x).max()),sha256=sha(folder/f'{tag}.wav'))
        for path in folder.glob('original_source_*.wav'):
            source=path.stem.removeprefix('original_source_')
            for tag in ['steady','varying']:
                assert path.read_bytes()==(folder/f'{tag}_source_{source}.wav').read_bytes() or source in ['exhaust_left','exhaust_right','body'],source
        difference={tag:dict(difference_to_original_db=rms(x-arrays['original'])-rms(arrays['original']),
                            raw_rms_change_db=rms(x)-rms(arrays['original'])) for tag,x in arrays.items() if tag!='original'}
        audition={}
        if crop:
            trimmed={tag:x[round(crop[0]*48000):round(crop[1]*48000)].copy() for tag,x in arrays.items()}
            for x in trimmed.values():
                ramp=.5-.5*np.cos(np.linspace(0,np.pi,240));x[:240]*=ramp[:,None];x[-240:]*=ramp[::-1,None]
            gains={tag:10**((-23-rms(x))/20) for tag,x in trimmed.items()}
            trim=min(1,.85/max(float(abs(x).max())*gains[tag] for tag,x in trimmed.items()))
            for tag,x in trimmed.items():
                gain=gains[tag]*trim;path=folder/f'audition_{tag}.wav'
                sf.write(path,x*gain,48000,subtype='PCM_24')
                audition[tag]=dict(file=path.name,sha256=sha(path),gain_db=float(20*np.log10(gain)),
                    crop_seconds=crop,endpoint_fade_ms=5,rms_dbfs=rms(x*gain))
            page[name]=dict(label=label,takes={tag:f'../renders/firing_pulse_v1/{name}/'+row['file'] for tag,row in audition.items()},
                           gains={tag:row['gain_db'] for tag,row in audition.items()})
        result['cases'][name]=dict(label=label,capture=capture,input_sha256=sha(take),variants=variants,difference=difference,
            auditions=audition,identical_original_source_and_drive_states=True,unchanged_seven_other_source_stems=True)
        if name=='high':
            run([PROBE,take,folder/'varying_714',2,12])
            for path in folder.glob('varying_source_*.wav'):
                assert path.read_bytes()==(folder/path.name.replace('varying_','varying_714_',1)).read_bytes()
            for suffix in ['.csv','_state.csv']:
                assert (folder/('varying'+suffix)).read_bytes()==(folder/('varying_714'+suffix)).read_bytes()
            result['layout714']=dict(identical_ten_sources_and_drive_state=True,physical_array_listening=False)
        print(json.dumps(dict(case=name,difference=difference)),flush=True)
    result['page_data']=page
    template=ROOT/'tools/firing_pulse_page.html'
    text=template.read_text(encoding='utf-8').replace('__DATA__',json.dumps(page,ensure_ascii=False).replace('</','<\\/'))
    (ROOT/'research/逐缸压力源试听V1.html').write_text(text,encoding='utf-8')
    result['files']={p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*') if p.is_file()}
    (OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

if __name__=='__main__':main()
