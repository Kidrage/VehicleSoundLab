"""Prepare phase-aligned audition deltas; validate against the frozen C host."""
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from runtime_review import ROOT,sha,rms
import numpy as np
import soundfile as sf

SOURCE=ROOT/'renders/character_v1'
OUT=ROOT/'renders/character_tuner_v1'
PROBE=ROOT/'baselines/character_v1/bin/character_probe.exe'


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    if (OUT/'manifest.json').exists():raise SystemExit('Preserve completed tuner assets.')
    original=read(SOURCE/'results.json');frozen=ROOT/'baselines/character_v1'
    for item in read(frozen/'manifest.json')['files']:assert sha(frozen/item['path'])==item['sha256']
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'checks').mkdir(exist_ok=True)
    cases={};arrays={};checks={}
    for name,row in original['cases'].items():
        variants={}
        for tag in ['base','pressure','structure','combined']:
            path=SOURCE/f'{name}_{tag}.wav';assert sha(path)==row['variants'][tag]['sha256']
            x,rate=sf.read(path,always_2d=True);assert rate==48000 and x.shape[1]==2 and np.isfinite(x).all()
            variants[tag]=x
        b=variants['base'];p=(variants['pressure']-b).astype(np.float32);s=(variants['structure']-b).astype(np.float32)
        corners=[b,b+p,b+s,b+p+s]
        peak=max(float(abs(x).max()) for x in corners);assert peak<.94
        # One fixed gain for the entire parameter square, never per setting.
        gain=min(10**((-23-max(map(rms,corners)))/20),.80/peak)
        assets={'base':dict(path='../character_v1/'+name+'_base.wav',sha256=sha(SOURCE/f'{name}_base.wav'))}
        for tag,data in [('pressure',p),('structure',s)]:
            path=OUT/f'{name}_{tag}_delta.wav';sf.write(path,data,48000,subtype='FLOAT')
            assets[tag]=dict(path=path.name,sha256=sha(path))
        arrays[name]=(b,p,s)
        cases[name]=dict(label=row['label'],frames=len(b),sample_rate=rate,channels=2,assets=assets,
            audition_gain=gain,audition_gain_db=float(20*np.log10(gain)),raw_parameter_square_peak=peak,
            loop_frames=[120000,230400] if name in ['low','mid','high'] else [0,len(b)],
            take_sha256=row['take_sha256'],listening_condition='Same fixed take; stereo listener mix. Two deltas include their existing source IR and spatial returns.')
    def validate(name,pressure,structure,tag):
        prefix=OUT/'checks'/f'{name}_{tag}'
        cmd=[str(PROBE),'render',str(SOURCE/f'{name}.vsltake'),str(prefix),str(pressure),str(structure),'2']
        done=subprocess.run(cmd,check=True,capture_output=True,text=True,timeout=90)
        actual,rate=sf.read(prefix.with_suffix('.wav'),always_2d=True);b,p,s=arrays[name]
        expected=b+pressure*p+structure*s
        error=float(abs(actual-expected).max());assert error<1e-7 and rate==48000
        return name+'_'+tag,dict(pressure=pressure,structure=structure,command=cmd,stdout=done.stdout,
            max_error=error,frames=len(actual),sha256=sha(prefix.with_suffix('.wav')))
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(validate,name,1,1,'corner11') for name in cases]
        jobs += [pool.submit(validate,name,.317,.731,'offgrid') for name in ['high','drive']]
        for future in as_completed(jobs):
            key,value=future.result();checks[key]=value;print('C comparison',key,value['max_error'],flush=True)
    manifest=dict(schema='vsl.character-tuner/1',experiment='character_v1',base_runtime='0.15.0',seed=48271,
        formula='base + pressure_amount * pressure_delta + structure_amount * structure_delta',
        scope='Offline rendered fixed-driving audition. No live engine/vehicle simulation; no reference-sample synthesis.',
        channels_preserved=True,normalization='One explicit shared constant per case over all four parameter-square corners; no dynamic gain normalization, compression or denoising.',
        valid_range=[0,1],cases=cases,C_checks=checks,source_results_sha256=sha(SOURCE/'results.json'),
        source_verification_sha256=sha(SOURCE/'verification.json'),frozen_probe_sha256=sha(PROBE))
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    print('Prepared six stereo groups, twelve phase-aligned deltas, eight new direct C checks.',flush=True)


if __name__=='__main__':main()
