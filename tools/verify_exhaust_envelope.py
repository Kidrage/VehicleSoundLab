"""Actual fired-branch shape check, preservation audit and candidate freeze."""
import csv
import json
import shutil
from runtime_review import ROOT, sha
from reference_segments import read_segment, checked_source
from spectral_coordinates import smooth_spectra
import numpy as np
import soundfile as sf

OUT = ROOT/'renders/exhaust_envelope_v1'
SNAP = ROOT/'baselines/exhaust_envelope_v1'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def actual_shapes(recipe):
    audio, rate, provenance = read_segment('A_exterior_blips', 'exterior_dynamic_observation')
    hz, at, db = smooth_spectra(audio, rate)
    at += provenance['source_seconds'][0]
    mask = (hz >= 1500) & (hz <= 8000)
    targets = {}
    for name, interval in [('training', (238.18,238.52)), ('first_later', (238.70,239.)), ('second', (241.22,241.62))]:
        selected = (at >= interval[0]) & (at <= interval[1])
        shape = db[selected].mean(axis=(0,1))[mask]
        targets[name] = shape-shape.mean()
    rows, input_equality, state_hashes = {}, {}, {}
    for case in ['mid', 'high']:
        path = ROOT/f'renders/v0.16.0/{case}_base.csv'
        with path.open() as stream:
            trace = [r for r in csv.DictReader(stream) if 2.5 <= float(r['seconds']) <= 4.8]
        assert trace and all(r['fuel_mode']=='FIRE' and float(r['firing_excitation'])==1 and
            float(r['pressure_texture_mix'])==0 and float(r['structure_transfer_mix'])==0 for r in trace)
        state_hashes[case] = sha(path)
        fired, sr = sf.read(OUT/f'{case}_base_fired_input.wav', always_2d=True)
        for c, obj in enumerate(['exhaust_left', 'exhaust_right']):
            source, r = sf.read(ROOT/f'renders/exhaust_phase_v1/{case}_base_source_{obj}.wav')
            assert r == sr == rate
            selected = slice(round(2.5*sr), round(4.8*sr))
            assert np.array_equal(fired[selected,c], source[selected])
        input_equality[case] = True
        rows[case] = {}
        for tag in ['base','half','full']:
            x, sr = sf.read(OUT/f'{case}_{tag}_fired_output.wav', always_2d=True)
            frequency, times, shape = smooth_spectra(x, sr)
            assert np.array_equal(hz, frequency)
            selected = (times >= 2.5) & (times <= 4.8)
            actual = shape[selected].mean(axis=(0,1))[mask]
            actual -= actual.mean()
            scores = {name:float(np.sqrt(np.mean((actual-target)**2))) for name,target in targets.items()}
            rows[case][tag] = dict(fired_output_sha256=sha(OUT/f'{case}_{tag}_fired_output.wav'), shape_proxy_rmse_db=scores)
        assert abs(rows[case]['base']['shape_proxy_rmse_db']['training']-
                   recipe['source_shape_proxy_scores'][case]['base']) < 1e-10
    return dict(result='pass', reference=provenance, native_states='FIRE, unit firing gate, zero character strengths in selected steady analysis windows',
                native_trace_sha256=state_hashes, calibration_proxy_equals_actual_fired_input=input_equality,
                actual_C_export_scores=rows,
                interpretation='Actual fired C export compared to unmatched mixed-reference geometric log-PSD shape with mean removed. No loudness/phase/space fidelity, matched-state fit or realism established.')


def main():
    if (OUT/'verification.json').exists() or SNAP.exists():
        raise SystemExit('Preserve completed exhaust_envelope_v1 snapshot.')
    result = read(OUT/'results.json');recipe = read(OUT/'recipe.json')
    assert result['recipe_sha256'] == sha(OUT/'recipe.json')
    assert recipe['generated_profile_sha256'] == sha(ROOT/'experiments/exhaust_envelope_v1/recipe.inc')
    assert recipe['script_sha256'] == sha(ROOT/'tools/prepare_exhaust_envelope.py')
    assert recipe['spectral_tools_sha256'] == sha(ROOT/'tools/spectral_coordinates.py')
    for source in [result, recipe]:
        for name,digest in source['inputs'].items():
            assert sha(ROOT/name) == digest, name
    for name,digest in result['files'].items():
        assert sha(OUT/name) == digest, name
    for name,digest in result['binaries'].items():
        assert sha(ROOT/name) == digest, name
    browser = read(OUT/'browser_qa.json')
    assert browser['result']=='pass' and browser['metadata_loads']==27 and browser['reference_metadata_loads']==2
    assert browser['position_preserved'] and browser['muted_playback_switch_preserved'] and browser['reference_playback_mutual_exclusion']
    assert not browser['mobile_horizontal_overflow'] and not browser['javascript_errors']
    ctest = (OUT/'ctest.txt').read_text()
    assert '100% tests passed out of 1' in ctest and 'fired_exhaust_envelope_contracts ...   Passed' in ctest
    actual = actual_shapes(recipe)
    (OUT/'actual_shape.json').write_text(json.dumps(actual,indent=2,allow_nan=False),encoding='utf-8')
    native = read(ROOT/'renders/v0.16.0/verification.json')
    for name,digest in native['binaries'].items():
        assert sha(ROOT/'build-v016/Release'/name)==digest, name
    frozen = read(ROOT/'baselines/v0.16.0/manifest.json');source_count=0
    for item in frozen['files']:
        name=item['path']
        if name.startswith(('src/','tests/')) or name in ['CMakeLists.txt','Launch.cmd','Launch-character.cmd','build.ps1','AGENTS.md']:
            assert sha(ROOT/name)==item['sha256'],name
            source_count+=1
    v011 = ['src/core/dna.c','src/core/high_orders.c','src/core/exhaust_spectrum.c','src/profiles/high_orders.c']
    for name in v011:
        assert sha(ROOT/name)==sha(ROOT/'baselines/v0.11.0'/name), name
    history={}
    for folder in sorted((ROOT/'baselines').iterdir()):
        if not (folder/'manifest.json').exists():continue
        manifest=read(folder/'manifest.json')
        for item in manifest['files']:
            assert sha(folder/item['path'])==item['sha256'],str(folder/item['path'])
        history[folder.name]=len(manifest['files'])
    assert len(history)==22 and history['spectral_coordinates_v1']==27, history
    media={name:checked_source(name) for name in ['A','B']}
    paths=['tools/prepare_exhaust_envelope.py','tools/render_exhaust_envelope.py','tools/verify_exhaust_envelope.py',
           'tools/spectral_coordinates.py','tools/runtime_review.py','tools/reference_segments.py','tools/review_pairs.py',
           'tools/comparison_page.py','tools/verify_review_player.cjs','references/segments_v1.json',
           'research/主排气谱形实验V1.md','research/主排气谱形试听V1.html',
           'research/goal_progress_exhaust_envelope_v1.json','README.md',
           'build-experiment-exhaust-envelope/envelope_engine.c','build-experiment-exhaust-envelope/envelope_excitation.c',
           'build-experiment-exhaust-envelope/envelope_take.c',
           'build-experiment-exhaust-envelope/Release/exhaust_envelope_probe.exe',
           'build-experiment-exhaust-envelope/Release/exhaust_envelope_checks.exe',
           'build-experiment-exhaust-envelope/Release/exhaust_envelope.lib','build-v016/Release/vsl_core.lib']
    paths += [str(p.relative_to(ROOT)).replace('\\','/') for p in sorted((ROOT/'experiments/exhaust_envelope_v1').iterdir()) if p.is_file()]
    report=dict(result='pass',experiment='exhaust_envelope_v1',runtime='0.16.0 unchanged',
                primary_results_sha256=sha(OUT/'results.json'),actual_shape_sha256=sha(OUT/'actual_shape.json'),
                browser_qa_sha256=sha(OUT/'browser_qa.json'),native_source_and_contract_files_unchanged=source_count,
                native_binaries_unchanged=native['binaries'],preserved_snapshots=history,approved_media=media,
                original_v011_files_unchanged={name:sha(ROOT/name) for name in v011},
                source_and_build_files={name:sha(ROOT/name) for name in paths},
                artifacts={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file()},
                scope='Concrete bounded C voicing and pipeline checks only. No new reference playback, stochastic detail, width or subjective acceptance; full goal active.')
    (OUT/'verification.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    SNAP.mkdir()
    for name in paths:
        target=SNAP/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    for path in sorted(OUT.iterdir()):
        if path.is_file() and (path.suffix in ['.json','.txt','.png'] or path.name.startswith(('audition_','reference_','impulse_'))):
            target=SNAP/'renders/exhaust_envelope_v1'/path.name
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    files=[dict(path=str(p.relative_to(SNAP)).replace('\\','/'),sha256=sha(p)) for p in sorted(SNAP.rglob('*')) if p.is_file()]
    manifest=dict(experiment='exhaust_envelope_v1',base_runtime='0.16.0 unchanged',files=files,
                  native_source_manifest_sha256=sha(ROOT/'baselines/v0.16.0/manifest.json'),
                  full_float_render_inventory_sha256=sha(OUT/'results.json'),
                  storage='Auditions, references, impulses, source, generated dispatch, linked library, probes and evidence included. Full float mixes,source stems and fired taps retained at original hash-bound render paths.',
                  status='Frozen unaccepted bounded fixed-Hz fired-pressure voicing; no physical target transfer or realism inferred.')
    (SNAP/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    for item in files:
        assert sha(SNAP/item['path'])==item['sha256'],item['path']
    print(json.dumps(dict(result='pass',snapshot_files=len(files),preserved_snapshots=len(history),
                          native_source_files_unchanged=source_count,actual_shape_scores=actual['actual_C_export_scores']),indent=2))


if __name__=='__main__':main()
