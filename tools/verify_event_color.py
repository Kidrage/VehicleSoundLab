"""Verify and freeze an optional candidate without changing the native runtime."""
import csv
import json
import shutil
from runtime_review import ROOT,sha
from reference_segments import read_segment
import numpy as np
import soundfile as sf

OUT=ROOT/'renders/event_color_v1'
SNAP=ROOT/'baselines/event_color_v1'


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def rows(path):
    with path.open(encoding='utf-8') as f:return list(csv.DictReader(f))


def main():
    if (OUT/'verification.json').exists() or SNAP.exists():raise SystemExit('Preserve completed event_color_v1.')
    result=read(OUT/'results.json')
    for name,digest in result['sources'].items():assert sha(ROOT/name)==digest,name
    for name,digest in result['files'].items():assert sha(OUT/name)==digest,name
    analysis=read(OUT/'analysis.json');assert analysis['result']=='pass'
    for name,digest in analysis['inputs'].items():assert sha(OUT/name)==digest,name
    assert analysis['independent_Butterworth_double_oracle_max_error']<1e-12
    assert max(analysis['independently_predicted_source_delta_max_float_error'].values())<1.3e-7
    auditions={};linearity={};denied={}
    for name,row in result['cases'].items():
        folder=OUT/name;pair={};states={};signals={}
        for tag,meta in row['auditions'].items():
            x,sr=sf.read(folder/f'{tag}.wav',always_2d=True)
            y,ar=sf.read(folder/meta['file'],always_2d=True);assert sr==ar==48000 and x.shape==y.shape
            fade=np.ones(len(x));ramp=.5-.5*np.cos(np.linspace(0,np.pi,240));fade[:240]=ramp;fade[-240:]=ramp[::-1]
            error=float(abs(y-x*10**(meta['gain_db']/20)*fade[:,None]).max())
            assert sf.info(folder/meta['file']).subtype=='PCM_24' and error<1.3e-7 and abs(y).max()<.850001
            assert sha(folder/meta['file'])==meta['sha256']
            pair[tag]=dict(gain_db=meta['gain_db'],max_PCM24_error=error)
            states[tag]=rows(folder/f'{tag}_state.csv');signals[tag]=x
        assert len({v['gain_db'] for v in pair.values()})==1
        keys=['frame','native_state_fnv1a64','events_l','events_r']
        assert all([tuple(r[k] for k in keys) for r in states['fixed']]==[tuple(r[k] for k in keys) for r in states[tag]] for tag in ['half','full'])
        error=float(abs(signals['half']-.5*(signals['fixed']+signals['full'])).max())
        assert error<6e-8,(name,error);linearity[name]=error
        trace=rows(folder/'full.csv');assert len(trace)==len(states['full']);checked=0
        for i in range(1,len(trace)):
            if float(trace[i-1]['fuel_command'])==float(trace[i]['fuel_command'])==0:
                for k in ['events_l','events_r']:assert states['full'][i][k]==states['full'][i-1][k]
                checked+=1
        auditions[name]=pair;denied[name]=checked
    assert denied['lift']>100
    reference_checks={}
    for name,meta in result['references'].items():
        use='exterior_spectral_observation' if name.endswith('low_rev') else 'exterior_dynamic_observation'
        x,sr,provenance=read_segment(name,use)
        assert provenance==meta['provenance']
        path=OUT/(meta['file'].split('/')[-1]);y,ar=sf.read(path,always_2d=True)
        assert sr==ar and x.shape==y.shape and sha(path)==meta['sha256']
        fade=np.ones(len(x));n=round(sr*.005);ramp=.5-.5*np.cos(np.linspace(0,np.pi,n));fade[:n]=ramp;fade[-n:]=ramp[::-1]
        error=float(abs(y-.5*x*fade[:,None]).max());assert error<1.3e-7
        reference_checks[name]=dict(sha256=sha(path),max_PCM24_error=error,unchanged_master_sha256=provenance['master_sha256'])
    browser=read(OUT/'browser_qa.json')
    assert browser['result']=='pass' and browser['audio_metadata_loads']==21 and browser['reference_loads']==2
    assert browser['reference_and_synth_mutual_exclusion']
    assert result['bed714']['identical_ten_source_stems'] and result['bed714']['identical_native_and_color_states']
    log=ROOT/'build-experiment-event-color/Testing/Temporary/LastTest.log'
    assert log.read_bytes().count(b'Test Passed.')==1;shutil.copy2(log,OUT/'ctest.log')
    native=read(ROOT/'baselines/v0.18.0/manifest.json');contracts={}
    for item in native['files']:
        name=item['path']
        if name.startswith(('src/','tests/')) or name in ['CMakeLists.txt','AGENTS.md','build.ps1','Launch.cmd','Launch-character.cmd','Launch-current.cmd','Launch-v017.cmd','Launch-response-shape.cmd']:
            assert sha(ROOT/name)==item['sha256'],name;contracts[name]=item['sha256']
    binaries={}
    for version,tag in [('0.15.0','v015'),('0.16.0','v016'),('0.17.0','v017'),('0.18.0','v018')]:
        current=read(ROOT/f'renders/v{version}/verification.json')['binaries']
        for name,digest in current.items():
            assert sha(ROOT/f'build-{tag}/Release'/name)==digest,(version,name)
            if version=='0.18.0':assert sha(ROOT/'baselines/v0.18.0/bin'/name)==digest,name
        binaries[version]=current
    for name in ['src/core/dna.c','src/core/high_orders.c','src/core/exhaust_spectrum.c','src/profiles/high_orders.c']:
        assert sha(ROOT/name)==sha(ROOT/'baselines/v0.11.0'/name),name
    history={p.parent.name:sha(p) for p in sorted((ROOT/'baselines').glob('*/manifest.json'))};assert len(history)==33
    names=set(result['sources'])|{'tools/analyze_event_color.py','tools/cycle_prediction.py','tools/verify_event_color.py',
        'tools/verify_event_color_ui.cjs','tools/runtime_review.py','research/主排气逐次形状实验V1.md',
        'research/goal_progress_event_color_v1.json','README.md'}
    names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'build-experiment-event-color').glob('color_*.c'))
    verification=dict(result='pass',experiment='event_color_v1',native_runtime='0.18.0 unchanged',
        independent_filter_and_source_oracles=analysis,shared_gain_PCM24_checks=auditions,
        actual_complete_mix_half_strength_linearity_max_error=linearity,stable_denied_fuel_trace_pairs=denied,
        reference_processing=reference_checks,browser=browser,native_contracts_unchanged=contracts,
        native_binaries_unchanged=binaries,previous_manifest_identities=history,
        sources={name:sha(ROOT/name) for name in sorted(names)},
        artifacts={p.relative_to(OUT).as_posix():sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()},
        subjective_status='Unaccepted main-pressure candidate. More waveform change and less cycle predictability are not evidence of realism. Broad goal active.')
    (OUT/'verification.json').write_text(json.dumps(verification,indent=2,allow_nan=False),encoding='utf-8')
    SNAP.mkdir()
    for name in sorted(names):
        target=SNAP/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    for path in sorted(OUT.rglob('*')):
        if path.is_file():
            target=SNAP/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    files=[dict(path=p.relative_to(SNAP).as_posix(),sha256=sha(p)) for p in sorted(SNAP.rglob('*')) if p.is_file()]
    (SNAP/'manifest.json').write_text(json.dumps(dict(experiment='event_color_v1',base_runtime='0.18.0 unchanged',files=files,
        status='Frozen main-pressure coloration candidate. Existing event/RNG/drive state retained. No subjective acceptance or native-default change.'),indent=2),encoding='utf-8')
    assert all(sha(SNAP/item['path'])==item['sha256'] for item in files)
    complete=dict(result='pass',snapshot_files=len(files),manifest_sha256=sha(SNAP/'manifest.json'),
        verification_sha256=sha(OUT/'verification.json'),native_contracts_unchanged=len(contracts),
        independent_double_oracle_error=analysis['independent_Butterworth_double_oracle_max_error'],
        subjective_status='Pending. Broad goal active.')
    (OUT/'freeze_complete.json').write_text(json.dumps(complete,indent=2),encoding='utf-8')
    print(json.dumps(complete,indent=2))


if __name__=='__main__':main()
