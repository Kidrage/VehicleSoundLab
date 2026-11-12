"""Render actual C candidates, verify coherent delta and one front route."""
import argparse,csv,json,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from catch_bloom_v1.measure import BANDS,RATE,powers
a.out.mkdir(parents=True,exist_ok=False)
for name in ('bin','renders','exact_sources'):(a.out/name).mkdir()
for path in [Path(__file__),*list((repo/'tools/catch_bloom_v1').glob('*.py'))]:
    dest=a.out/'exact_sources'/path.relative_to(repo);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
r=dict(result='running',commands=[],cases=[],human_accepted=False,device_tested=False)
def run(cmd):
    cmd=list(map(str,cmd));done=subprocess.run(cmd,cwd=repo,capture_output=True,timeout=120)
    name=f'command_{len(r["commands"]):02}.log';(a.out/name).write_bytes(done.stdout+done.stderr)
    r['commands'].append(dict(argv=cmd,exit_code=done.returncode,log=name,sha256=sha(a.out/name)))
    assert done.returncode==0,name
def audio(path):
    y,rate=sf.read(path,always_2d=True);assert rate==RATE and len(y)==6*RATE and np.isfinite(y).all();return y
try:
    build=a.workspace/'references/analysis/catch_bloom_v1/build2';fit=a.workspace/'references/analysis/catch_bloom_v1/fit2'
    bp=json.loads((build/'report.json').read_text());fp=json.loads((fit/'report.json').read_text())
    assert bp['result']=='isolated_adapter_built_and_checked' and fp['result']=='coarse_support_candidate_fitted'
    for name,digest in bp['source_sha256'].items():assert sha(repo/name)==digest,name
    binary=build/'bin/catch_bloom_probe.exe';assert sha(binary)==bp['binaries'][binary.name]
    shutil.copy2(binary,a.out/'bin'/binary.name);binary=a.out/'bin'/binary.name
    profile=fit/fp['profile']['path'];assert sha(profile)==fp['profile']['sha256']
    shutil.copy2(profile,a.out/profile.name);profile=a.out/profile.name
    model=repo/'voices/startup_settle_v1/A start cabin settle.model';starter=repo/'voices/startup_drive_v1/A cabin motion.start'
    data=np.load(fit/'fit.npz');r['profile_sha256']=sha(profile);r['binary_sha256']=sha(binary)
    cases={}
    for channels in (2,12):
        for amount in (0,.5,1):
            key=f'{channels}_{amount:.1f}';prefix=a.out/'renders'/key
            run([binary,model,starter,profile,prefix,amount,channels])
            values={name:audio(prefix.with_name(prefix.name+'_'+name+'.wav')) for name in ('mix','base','raw','dna','startup','bloom')}
            for name in ('base','raw','dna','startup'):
                old=build/'renders'/('base2_'+name+'.wav')
                if channels==2 or name not in ('base',):assert prefix.with_name(prefix.name+'_'+name+'.wav').read_bytes()==old.read_bytes(),(key,name)
            with prefix.with_name(prefix.name+'_trace.csv').open() as stream:trace=list(csv.DictReader(stream))
            assert len(trace)==1200 and {int(row['lifecycle']) for row in trace}==set(range(6)) and int(trace[-1]['start_events'])==2
            if channels==12:
                assert np.array_equal(values['mix'][:,:2],cases[f'2_{amount:.1f}']['mix'])
                assert np.max(abs(values['mix'][:,2:]))==0
                for name in ('raw','dna','startup','bloom'):
                    assert np.array_equal(values[name],cases[f'2_{amount:.1f}'][name]),(key,name)
            reference=data['expected_delta']*amount
            error=float(np.max(abs(values['bloom']-reference)));assert error<2e-7,error
            mix_error=float(np.max(abs(values['mix'][:,:2]-values['base'][:,:2]-.25*values['bloom'])));assert mix_error<2e-8,mix_error
            assert np.max(abs(values['mix']))<.9
            if amount==0:assert np.array_equal(values['mix'],values['base']) and np.max(abs(values['bloom']))==0
            cases[key]=values
            r['cases'].append(dict(key=key,channels=channels,amount=amount,peak=float(np.max(abs(values['mix']))),
                independent_python_delta_error=error,single_front_add_error=mix_error,starts=2,lifecycle_mask=63,
                driver_trace_sha256=sha(prefix.with_name(prefix.name+'_trace.csv')),
                WAV_sha256={name:sha(prefix.with_name(prefix.name+'_'+name+'.wav')) for name in values}))
    traces={row['driver_trace_sha256'] for row in r['cases']};assert len(traces)==1
    r['two_starts_band_observations']=[]
    _,before=powers(cases['2_0.0']['dna']);ts,after=powers(cases['2_1.0']['dna']+cases['2_1.0']['bloom'])
    for start in (.43,3.48):
        catch=(ts>=start+.05)&(ts<=start+.60)
        settle=(ts>=start+.90)&(ts<=start+1.65)
        r['two_starts_band_observations'].append(dict(catch_start_seconds=start,
            before_catch_to_settle_dB=(10*np.log10(before[catch].mean(axis=0)/before[settle].mean(axis=0))).tolist(),
            after_catch_to_settle_dB=(10*np.log10(after[catch].mean(axis=0)/after[settle].mean(axis=0))).tolist()))
    # Preserve full driver output as C baseline; an adapter, not native runtime.
    voices=repo/'voices/catch_bloom_v1';voices.mkdir(exist_ok=True);dest=voices/profile.name
    if dest.exists():assert dest.read_bytes()==profile.read_bytes()
    else:shutil.copy2(profile,dest)
    r.update(result='C_candidate_render_and_isolation_pass',driver_trace_identical=True,old_four_stems_unchanged=True,
        zero_mix_exact=True,front2_equal=True,other10_zero=True,native_UI_integrated=False,
        note='No duplicated source/controller; delta comes from enveloped DNA and is added once after the unchanged C renderer')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:r[k] for k in ('result','cases','two_starts_band_observations')}))
