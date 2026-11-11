"""Independent audition samples, native preservation audit and fixed snapshot."""
import json
import shutil
from runtime_review import ROOT, sha
from reference_segments import checked_source, CATALOG
from render_source_audition import validate
import numpy as np
import soundfile as sf

OUT = ROOT/'renders/source_audition_v1'
SNAP = ROOT/'baselines/source_audition_v1'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def audio(path):
    x, sr = sf.read(path, always_2d=True)
    assert sr == 48000 and np.isfinite(x).all()
    return x


def main():
    if SNAP.exists() or (OUT/'verification.json').exists():
        raise SystemExit('Preserve completed source_audition_v1 snapshot.')
    result = read(OUT/'results.json');page = read(OUT/'page.json');browser = read(OUT/'browser_qa.json')
    for inventory in ['files', 'inputs', 'source_files', 'binaries']:
        for name, digest in result[inventory].items():
            assert sha((OUT if inventory == 'files' else ROOT)/name) == digest, (inventory, name)
    assert page['base_results_sha256'] == sha(OUT/'results.json')
    assert page['page_sha256'] == sha(ROOT/page['page'])
    for name, digest in page['source_files'].items():
        assert sha(ROOT/name) == digest
    assert browser['result'] == 'pass' and browser['normal_audio_metadata_loads'] == 120
    assert browser['boosted_mechanical_loads'] == 8 and browser['reference_metadata_loads'] == 2
    for name in ['position_preserved_on_view_recipe_group', 'actual_muted_playback_and_switch',
        'obsolete_request_cannot_seek_or_play_current','boost_default_off_and_reset_on_full_remove_group_scene',
        'scene_change_stops_and_restarts_position','reference_mutual_exclusion','http_and_file_entry_checked',
        'visible_transport_play_pause_checked']:
        assert browser[name], name
    assert not browser['mobile_horizontal_overflow'] and not browser['javascript_errors']
    assert 'Test Passed.' in (OUT/'ctest_original.log').read_text(errors='replace')
    assert 'source_audition_contracts' in (OUT/'ctest_original.log').read_text(errors='replace')
    checks, quantization = {}, {}
    for name, row in result['cases'].items():
        prefix = OUT/name
        native = ROOT/f'renders/v0.16.0/{name}.vsltake' if not name.endswith('_714') else None
        actual = validate(prefix, native)
        assert all(actual[k] == row[k] for k in actual), name
        checks[name] = actual
        if not native:
            continue
        scene, recipe = name.rsplit('_', 1)
        gain_db = page['page_data'][scene]['gain_db'];gain = 10**(gain_db/20)
        peak_error = 0
        for mode, record in row['auditions'].items():
            path = OUT/record['file'];assert sha(path) == record['sha256']
            assert sf.info(path).subtype == 'PCM_24' and record['gain_db'] == gain_db
            x = audio(path);raw = audio(OUT/f'{name}_{mode}.wav')
            assert x.shape == raw.shape and abs(x).max() <= .85
            error = float(abs(x-raw*gain).max())
            assert error <= 2**-23+1e-12, (name, mode, error)
            peak_error = max(peak_error, error)
        # PCM quantization must not obscure the same linear source partition.
        full = audio(OUT/row['auditions']['full']['file']);summed = np.zeros_like(full)
        closures = {}
        for group in result['group_labels']:
            solo = audio(OUT/row['auditions']['solo_'+group]['file'])
            without = audio(OUT/row['auditions']['without_'+group]['file'])
            error = float(abs(solo+without-full).max())
            assert error < 4*2**-23
            closures[group] = error;summed += solo
        sum_error = float(abs(summed-full).max());assert sum_error < 9*2**-23
        quantization[name] = dict(maximum_common_gain_PCM24_error=peak_error,
            PCM24_complement_errors=closures, PCM24_partition_max_error=sum_error)
    boosts = {}
    for name, row in page['optional_mechanical_boost'].items():
        path = OUT/row['file'];assert sha(path) == row['sha256'] and row['extra_gain_db'] == 24
        scene, recipe = name.rsplit('_', 1)
        assert row['total_gain_db'] == page['page_data'][scene]['gain_db']+24
        x = audio(path);raw = audio(OUT/f'{name}_solo_mechanical.wav')
        error = float(abs(x-raw*10**(row['total_gain_db']/20)).max())
        assert error < 2**-23+1e-12 and abs(x).max() < .85
        boosts[name] = dict(maximum_linear_PCM24_error=error, peak=float(abs(x).max()), extra_gain_db=24)
    native = read(ROOT/'renders/v0.16.0/verification.json')
    for name, digest in native['binaries'].items():
        assert sha(ROOT/'build-v016/Release'/name) == digest, name
    preserved = {}
    for item in read(ROOT/'baselines/v0.16.0/manifest.json')['files']:
        name = item['path']
        if name.startswith(('src/','tests/')) or name in ['CMakeLists.txt','Launch.cmd','Launch-character.cmd','build.ps1','AGENTS.md']:
            assert sha(ROOT/name) == item['sha256'], name
            preserved[name] = item['sha256']
    assert len(preserved) == 144
    v011 = ['src/core/dna.c','src/core/high_orders.c','src/core/exhaust_spectrum.c','src/profiles/high_orders.c']
    for name in v011:
        assert sha(ROOT/name) == sha(ROOT/'baselines/v0.11.0'/name), name
    media = {name:checked_source(name) for name in ['A','B']}
    history = {p.parent.name:sha(p) for p in sorted((ROOT/'baselines').glob('*/manifest.json'))}
    assert len(history) == 25
    paths = list(result['source_files'])+list(result['binaries'])+list(page['source_files'])
    paths += ['tools/verify_source_audition.py','tools/verify_source_audition_ui.cjs',
        'tools/runtime_review.py','tools/reference_segments.py','references/segments_v1.json',
        'research/声源分层试听V1.html','research/声源分层试听说明V1.md',
        'research/goal_progress_source_audition_v1.json','README.md']
    paths += [name for name in result['inputs'] if name.endswith('.vsltake')]
    paths = sorted(set(paths))
    verification = dict(result='pass',study='source_audition_v1',runtime='0.16.0 unchanged',
        source_groups=7,stereo_takes=8,normal_auditions=120,optional_mechanical_auditions=8,
        repeated_float_closure_checks=checks,independent_PCM24_checks=quantization,independent_boost_checks=boosts,
        native_source_and_contract_files_unchanged=preserved,native_binaries_unchanged=native['binaries'],
        approved_media=media,catalog_sha256=sha(CATALOG),
        previous_snapshot_manifest_identities=history,
        source_and_build_files={name:sha(ROOT/name) for name in paths},
        artifacts={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file()},
        scope='Actual fixed-voicing spatial source views and sample/control identity. No subjective acceptance, physical-array listening, source-causal excitation ablation or new native code. Previous manifests recorded by identity; not a fresh content audit of all old snapshots.')
    (OUT/'verification.json').write_text(json.dumps(verification, indent=2, allow_nan=False), encoding='utf-8')
    SNAP.mkdir()
    for name in paths:
        target = SNAP/name;target.parent.mkdir(parents=True, exist_ok=True);shutil.copy2(ROOT/name, target)
    for path in sorted(OUT.iterdir()):
        if path.is_file() and (path.suffix in ['.json','.log','.png'] or path.name.startswith('audition_')):
            target = SNAP/path.relative_to(ROOT);target.parent.mkdir(parents=True, exist_ok=True);shutil.copy2(path, target)
    files = [dict(path=p.relative_to(SNAP).as_posix(),sha256=sha(p)) for p in sorted(SNAP.rglob('*')) if p.is_file()]
    manifest = dict(study='source_audition_v1',runtime='0.16.0 unchanged',files=files,
        native_source_manifest_sha256=sha(ROOT/'baselines/v0.16.0/manifest.json'),
        raw_render_inventory_sha256=sha(OUT/'results.json'),
        storage='128 auditions, player, sources, generated observer/scheduler/take, probes/checks/library, input takes and evidence included. Raw float mixes, source stems and native traces remain at original local paths bound by results.json. Native source dependency is preserved separately in baselines/v0.16.0; approved reference derivatives/media remain at their original hash-bound paths.',
        status='Frozen acoustic-object listening tool using existing unaccepted voicing, not a new tonal candidate or realism acceptance.')
    (SNAP/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    assert all(sha(SNAP/item['path']) == item['sha256'] for item in files)
    print(json.dumps(dict(result='pass',snapshot_files=len(files),prior_manifests=len(history),
        native_files_unchanged=len(preserved),normal_auditions=120,explicit_boosted_solos=8,
        maximum_float_partition_error=max(row['sum_groups_max_error'] for row in checks.values()),
        maximum_auxiliary_peak=max(row['peak'] for row in boosts.values())), indent=2))


if __name__ == '__main__':
    main()
