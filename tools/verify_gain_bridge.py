"""Independent control/sideband checks, preservation and fixed review snapshot."""
import json
import shutil
from runtime_review import ROOT, sha, rms
from reference_segments import checked_source, CATALOG
import numpy as np
import soundfile as sf

OUT=ROOT/'renders/gain_bridge_v1'
SNAP=ROOT/'baselines/gain_bridge_v1'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def audio(path):
    x,sr=sf.read(path,always_2d=True);assert sr==48000 and np.isfinite(x).all()
    return x


def main():
    if (OUT/'verification.json').exists() or SNAP.exists():
        raise SystemExit('Preserve frozen gain_bridge_v1.')
    result=read(OUT/'results.json');page=read(OUT/'page.json');browser=read(OUT/'browser_qa.json')
    for kind in ['files','inputs','sources','binaries','retained_initial_overlap']:
        for name,digest in result[kind].items():
            assert sha((OUT if kind in ['files','retained_initial_overlap'] else ROOT)/name)==digest,(kind,name)
    assert page['base_results_sha256']==sha(OUT/'results.json') and page['page_sha256']==sha(ROOT/page['page'])
    for name,digest in page['sources'].items():
        assert sha(ROOT/name)==digest,name
    assert browser['result']=='pass' and browser['audio_metadata_loads']==8
    for key in ['position_preserved','actual_muted_playback_and_transport','playing_state_preserved',
        'obsolete_response_isolation','case_change_stops_at_zero','http_and_file_entry','figure_loaded']:
        assert browser[key],key
    assert not browser['mobile_horizontal_overflow'] and not browser['javascript_errors']
    log=(OUT/'ctest_original.log').read_text(errors='replace')
    assert 'gain_bridge_contracts' in log and 'Test Passed.' in log
    gain_checks,quantization,window_checks={},{},{}
    for case,row in result['cases'].items():
        gain_checks[case]={}
        for name,record in row['control_checks'].items():
            pairs=audio(OUT/f'{case}_hold_gain_{name}.wav')
            assert np.array_equal(pairs,audio(OUT/f'{case}_ramp_gain_{name}.wav'))
            # Prefix sums provide an independent finite-window calculation,
            # separate from the C ramp and renderer's scipy.signal.lfilter.
            prefix=np.concatenate(([0.],np.cumsum(pairs[:,0],dtype=np.float64)))
            stop=np.arange(1,len(pairs)+1);start=np.maximum(0,stop-240)
            expected=(prefix[stop]-prefix[start])/240
            error=float(abs(expected-pairs[:,1]).max());assert error<1.5e-7
            held_change=abs(np.diff(pairs[:,0],prepend=0))
            assert np.all(held_change[np.arange(len(pairs))%240!=0]==0)
            assert abs(record['maximum_ramp_step']*240-record['maximum_held_step'])<5e-12
            gain_checks[case][name]=dict(independent_prefix_window_error=error,
                held_control_changes_only_at_200Hz_edges=True,
                maximum_held_step=record['maximum_held_step'],maximum_C_ramp_step=record['maximum_ramp_step'])
        arrays={method:audio(OUT/f'{case}_{method}.wav') for method in ['hold','ramp']}
        for method,x in arrays.items():
            entry=row['audition'][method];file=OUT/entry['file'];assert sha(file)==entry['sha256']
            assert sf.info(file).subtype=='PCM_24' and abs(x).max()<.95
            y=audio(file);error=float(abs(y-x*10**(entry['gain_db']/20)).max())
            assert error<=2**-23+1e-12 and abs(y).max()<=.85
            quantization[case+'_'+method]=error
        assert row['audition']['hold']['gain_db']==row['audition']['ramp']['gain_db']
        difference=arrays['ramp']-arrays['hold'];selected=difference[2*48000:]
        window_checks[case]=dict(complete_difference_rms_dbfs=rms(difference),
            difference_relative_to_full_rms_db=rms(difference)-rms(arrays['hold']),
            after2s_difference_rms_dbfs=rms(selected),after2s_difference_peak=float(abs(selected).max()))
    full=audio(OUT/'high_hold.wav');delta=audio(OUT/'high_ramp.wav')-full
    assert float(abs(delta[-96000:]).max())<2e-12
    # Full complex frequency response, not only the renderer's sine magnitude.
    carrier=audio(OUT/'control_carrier.wav');n=len(carrier);spectrum=np.fft.rfft(carrier,axis=0)
    complex_checks=[]
    for row in result['diagnostic_carrier']:
        offset=row['offset_hz'];index=round((2048+offset)*n/48000)
        actual=spectrum[index,1]/spectrum[index,0]
        independent=np.exp(-2j*np.pi*offset*np.arange(240)/48000).mean()
        error=float(abs(actual-independent));assert error<2e-6
        complex_checks.append(dict(offset_hz=offset,complex_response_error=error,
            actual_gain_db=float(20*np.log10(abs(actual))),actual_phase_radians=float(np.angle(actual))))
    retained=OUT/'initial_carrier_overlap';old_gain=audio(retained/'control_gain.wav');old_carrier=audio(retained/'control_carrier.wav')
    g=np.fft.fft(old_gain,axis=0)/len(old_gain);a=np.fft.fft(old_carrier,axis=0)/len(old_carrier)
    overlaps=[]
    for offset in [7,193,207,393,407]:
        N=len(old_gain);expected=.5*(g[round(offset*N/48000)]+g[round((4000+offset)*N/48000)])
        error=float(abs(a[round((2000+offset)*N/48000)]-expected).max());assert error<1e-9
        overlaps.append(dict(offset_hz=offset,independent_two_branch_FFT_error=error))
    native=read(ROOT/'renders/v0.16.0/verification.json');preserved={}
    for name,digest in native['binaries'].items():
        assert sha(ROOT/'build-v016/Release'/name)==digest,name
    for item in read(ROOT/'baselines/v0.16.0/manifest.json')['files']:
        name=item['path']
        if name.startswith(('src/','tests/')) or name in ['CMakeLists.txt','Launch.cmd','Launch-character.cmd','build.ps1','AGENTS.md']:
            assert sha(ROOT/name)==item['sha256'],name;preserved[name]=item['sha256']
    assert len(preserved)==144
    v011=['src/core/dna.c','src/core/high_orders.c','src/core/exhaust_spectrum.c','src/profiles/high_orders.c']
    for name in v011:
        assert sha(ROOT/name)==sha(ROOT/'baselines/v0.11.0'/name),name
    media={name:checked_source(name) for name in ['A','B']}
    history={p.parent.name:sha(p) for p in sorted((ROOT/'baselines').glob('*/manifest.json'))}
    assert len(history)==26
    paths=sorted(set(list(result['sources'])+list(result['binaries'])+list(page['sources'])+[
        'tools/verify_gain_bridge.py','tools/verify_gain_bridge_ui.cjs','tools/runtime_review.py','tools/review_pairs.py',
        'tools/reference_segments.py','references/segments_v1.json','research/持续声层过渡实验V1.md',
        'research/持续声层过渡试听V1.html','research/goal_progress_gain_bridge_v1.json','README.md']+
        [name for name in result['inputs'] if name.endswith('.vsltake')]))
    verification=dict(result='pass',study='gain_bridge_v1',runtime='0.16.0 unchanged',
        independent_prefix_gain_checks=gain_checks,independent_complex_carrier_checks=complex_checks,
        retained_initial_overlap_checks=overlaps,independent_PCM24_errors=quantization,complete_render_difference_checks=window_checks,
        native_source_and_contract_files_unchanged=preserved,native_binaries_unchanged=native['binaries'],
        approved_media=media,catalog_sha256=sha(CATALOG),previous_snapshot_manifest_identities=history,
        source_and_build_files={name:sha(ROOT/name) for name in paths},
        artifacts={p.relative_to(OUT).as_posix():sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()},
        scope='Causal gain interpolation and exact control/source contracts in frozen-take offline experiments. No native version change, per-car fit, subjective acceptance or physical-array validation. Previous manifests identified, not a fresh audit of all historical file contents.')
    (OUT/'verification.json').write_text(json.dumps(verification,indent=2,allow_nan=False),encoding='utf-8')
    SNAP.mkdir()
    for name in paths:
        target=SNAP/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    for path in sorted(OUT.rglob('*')):
        if path.is_file() and (path.suffix in ['.json','.log','.png'] or path.name.startswith(('audition_','control_')) or 'initial_carrier_overlap' in path.parts):
            target=SNAP/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    files=[dict(path=p.relative_to(SNAP).as_posix(),sha256=sha(p)) for p in sorted(SNAP.rglob('*')) if p.is_file()]
    manifest=dict(study='gain_bridge_v1',base_runtime='0.16.0 unchanged',files=files,
        native_source_manifest_sha256=sha(ROOT/'baselines/v0.16.0/manifest.json'),raw_render_inventory_sha256=sha(OUT/'results.json'),
        storage='Auditions, C sources, generated scheduler/take, linked library, probes/checks, player, input takes, carrier controls, retained overlap test and evidence included. Full float engine renders/source stems/gain taps/traces remain at original hash-bound render paths. Native source dependency stays in baselines/v0.16.0.',
        status='Frozen optional interpolation experiment; complete mix differences small, no main timbre-cause or subjective improvement established.')
    (SNAP/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    assert all(sha(SNAP/item['path'])==item['sha256'] for item in files)
    print(json.dumps(dict(result='pass',snapshot_files=len(files),prior_manifests=len(history),native_files_unchanged=len(preserved),
        largest_prefix_gain_error=max(row['independent_prefix_window_error'] for case in gain_checks.values() for row in case.values()),
        largest_complex_response_error=max(row['complex_response_error'] for row in complex_checks),
        normal_auditions=8),indent=2))


if __name__=='__main__':
    main()
