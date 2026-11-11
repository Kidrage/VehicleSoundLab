"""Independent continuous impulse oracle and audition/source identity audit."""
import csv
import json
import shutil
from runtime_review import ROOT,sha
import numpy as np
import soundfile as sf
from scipy.integrate import quad

OUT=ROOT/'renders/response_shape_v1'
SNAP=ROOT/'baselines/response_shape_v1'


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def impulse_checks():
    # Frozen C coefficients are independently reproduced as continuous
    # functions; normalization uses numerical integration, not the C Gram law.
    definitions={'pressure':[(1050,.0014,.85),(2900,.00065,.52),(6100,.00032,.24)],
        'structure':[(610,.012,.26),(1180,.008,.42),(2240,.005,.60),(3870,.0035,.40),(5820,.0025,.22)]}
    result={}
    for kind,modes in definitions.items():
        def response(t,scale):
            return sum(weight*np.exp(-t/(decay*scale))*np.sin(2*np.pi*hz*t) for hz,decay,weight in modes)
        stop=40*max(m[1] for m in modes)*1.7
        base_energy,base_estimate=quad(lambda t:response(t,1)**2,0,stop,epsabs=1e-12,epsrel=1e-9,limit=3000)
        for coordinate in [-1,-.5,.5,1]:
            amount=abs(coordinate);scale=.55 if coordinate>0 else 1.7
            def mixed(t):return (1-amount)*response(t,1)+amount*response(t,scale)
            mixed_energy,estimate=quad(lambda t:mixed(t)**2,0,stop,epsabs=1e-12,epsrel=1e-9,limit=3000)
            normal=np.sqrt(base_energy/mixed_energy)
            path=OUT/f'impulse_{kind}_{coordinate:+.1f}.wav';x,sr=sf.read(path,always_2d=True)
            assert sr==192000 and x.shape==(96000,2) and sf.info(path).subtype=='FLOAT'
            t=np.arange(len(x))/sr;expected=np.column_stack([response(t,1),normal*mixed(t)])
            error=float(abs(x-expected).max());assert error<6e-8,(path,error)
            energies=np.sum(x*x,axis=0)/sr;relative_error=np.abs(energies/base_energy-1)
            assert relative_error.max()<3e-6,(kind,coordinate,relative_error)
            result[f'{kind}_{coordinate:+.1f}']=dict(max_float_sample_error=error,
                numerical_integral_base_energy=base_energy,numerical_integral_normalization=float(normal),
                sampled_energy_relative_error=relative_error.tolist(),integration_stop_seconds=stop,
                quadrature_error_estimate=float(max(base_estimate,estimate)),
                limits='Continuous isolated impulse normalization,not acoustic joules or fixed full-mix loudness. Quadrature errors are estimates; finite truncation and sampling remain.')
    return result


def main():
    if (OUT/'verification.json').exists() or SNAP.exists():raise SystemExit('Preserve frozen response_shape_v1.')
    result=read(OUT/'results.json')
    for name,digest in result['sources'].items():assert sha(ROOT/name)==digest,name
    for name,digest in result['files'].items():assert sha(OUT/name)==digest,name
    impulses=impulse_checks();auditions={};gates={}
    for name,row in result['cases'].items():
        folder=OUT/name;pair={};states={}
        for tag,meta in row['auditions'].items():
            source,sr=sf.read(folder/(tag+'.wav'),always_2d=True)
            audition,ar=sf.read(folder/meta['file'],always_2d=True)
            gain=10**(meta['gain_db']/20);error=float(abs(audition-source*gain).max())
            assert sr==ar==48000 and source.shape==audition.shape and error<1.3e-7
            assert sha(folder/meta['file'])==meta['sha256'] and abs(audition).max()<=.850001
            pair[tag]=dict(shared_gain_db=meta['gain_db'],max_PCM24_error=error)
            with (folder/(tag+'_state.csv')).open() as f:states[tag]=list(csv.DictReader(f))
        assert len({v['shared_gain_db'] for v in pair.values()})==1
        assert all([tuple(r[k] for k in ['frame','native_state_fnv1a64','pressure_events','structure_events']) for r in states['fixed']]==
            [tuple(r[k] for k in ['frame','native_state_fnv1a64','pressure_events','structure_events']) for r in states[tag]] for tag in ['half','full'])
        with (folder/'full.csv').open() as f:trace=list(csv.DictReader(f))
        checked=0
        for i in range(1,len(trace)):
            # Only blocks fully between two denied endpoints; native event/RNG
            # semantics and source trace also checked by C integration tests.
            if float(trace[i-1]['fuel_command'])==float(trace[i]['fuel_command'])==0:
                assert states['full'][i]['pressure_events']==states['full'][i-1]['pressure_events']
                assert states['full'][i]['structure_events']==states['full'][i-1]['structure_events'];checked+=1
        auditions[name]=pair;gates[name]=checked
    assert gates['lift']>100
    assert result['bed714']['identical_ten_source_stems'] and result['bed714']['identical_native_and_response_states']
    browser=read(OUT/'browser_qa.json');assert browser['result']=='pass' and browser['audio_metadata_loads']==18
    log=ROOT/'build-experiment-response-shape/Testing/Temporary/LastTest.log'
    assert log.read_bytes().count(b'Test Passed.')==1;shutil.copy2(log,OUT/'ctest.log')
    native=read(ROOT/'baselines/v0.17.0/manifest.json');preserved={}
    for item in native['files']:
        name=item['path']
        if name.startswith(('src/','tests/')) or name in ['CMakeLists.txt','AGENTS.md','build.ps1','Launch.cmd','Launch-character.cmd','Launch-current.cmd']:
            assert sha(ROOT/name)==item['sha256'],name;preserved[name]=item['sha256']
    binaries=read(ROOT/'renders/v0.17.0/verification.json')['binaries']
    for name,digest in binaries.items():assert sha(ROOT/'build-v017/Release'/name)==digest,name
    history={p.parent.name:sha(p) for p in sorted((ROOT/'baselines').glob('*/manifest.json'))};assert len(history)==31
    names=set(result['sources'])|{'tools/verify_response_shape.py','tools/verify_response_shape_ui.cjs','tools/runtime_review.py',
        'research/燃烧响应形状实验V1.md','research/goal_progress_response_shape_v1.json','README.md'}
    names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'build-experiment-response-shape').glob('response_*.c'))
    verification=dict(result='pass',experiment='response_shape_v1',independent_continuous_impulse_checks=impulses,
        audition_gain_checks=auditions,denied_firing_trace_pairs=gates,browser=browser,
        native_contracts_unchanged=preserved,native_binaries_unchanged=binaries,previous_manifest_identities=history,
        sources={name:sha(ROOT/name) for name in sorted(names)},
        artifacts={p.relative_to(OUT).as_posix():sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()},
        subjective_status='No acceptance inferred. C response shape prototype and actual audition ready; native defaults unchanged.')
    (OUT/'verification.json').write_text(json.dumps(verification,indent=2,allow_nan=False),encoding='utf-8')
    SNAP.mkdir()
    for name in sorted(names):
        target=SNAP/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    for path in sorted(OUT.rglob('*')):
        if path.is_file():
            target=SNAP/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    files=[dict(path=p.relative_to(SNAP).as_posix(),sha256=sha(p)) for p in sorted(SNAP.rglob('*')) if p.is_file()]
    (SNAP/'manifest.json').write_text(json.dumps(dict(experiment='response_shape_v1',base_runtime='0.17.0 unchanged',files=files,
        status='Frozen audible C response-shape candidate. No subjective acceptance or native promotion.'),indent=2),encoding='utf-8')
    assert all(sha(SNAP/item['path'])==item['sha256'] for item in files)
    complete=dict(result='pass',snapshot_files=len(files),manifest_sha256=sha(SNAP/'manifest.json'),
        verification_sha256=sha(OUT/'verification.json'),native_contracts_unchanged=len(preserved),
        max_impulse_float_error=max(r['max_float_sample_error'] for r in impulses.values()),
        subjective_status='Pending. Broad goal active.')
    (OUT/'freeze_complete.json').write_text(json.dumps(complete,indent=2),encoding='utf-8');print(json.dumps(complete,indent=2))


if __name__=='__main__':main()
