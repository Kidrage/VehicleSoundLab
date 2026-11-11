"""Audit and freeze the isolated phase candidate without changing native DSP."""
import json
import shutil
from pathlib import Path
from runtime_review import ROOT, sha
from reference_segments import checked_source

OUT = ROOT / 'renders/exhaust_phase_v1'
SNAP = ROOT / 'baselines/exhaust_phase_v1'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    if (OUT/'verification.json').exists() or SNAP.exists():
        raise SystemExit('Preserve completed exhaust_phase_v1 snapshot.')
    primary = read(OUT/'results.json')
    for name, digest in primary['files'].items():
        assert sha(OUT/name) == digest, name
    for name, digest in primary['inputs'].items():
        assert sha(ROOT/name) == digest, name
    for name, digest in primary['binaries'].items():
        assert sha(ROOT/name) == digest, name
    native = read(ROOT/'renders/v0.16.0/verification.json')
    for name, digest in native['binaries'].items():
        assert sha(ROOT/'build-v016/Release'/name) == digest, name
    frozen = read(ROOT/'baselines/v0.16.0/manifest.json')
    source_count = 0
    for item in frozen['files']:
        name = item['path']
        if name.startswith(('src/', 'tests/')) or name in [
                'CMakeLists.txt', 'Launch.cmd', 'Launch-character.cmd', 'build.ps1', 'AGENTS.md']:
            assert sha(ROOT/name) == item['sha256'], name
            source_count += 1
    v011 = ['src/core/dna.c', 'src/core/high_orders.c',
            'src/core/exhaust_spectrum.c', 'src/profiles/high_orders.c']
    for name in v011:
        assert sha(ROOT/name) == sha(ROOT/'baselines/v0.11.0'/name), name
    history = {}
    for folder in sorted((ROOT/'baselines').iterdir()):
        if not (folder/'manifest.json').exists():
            continue
        manifest = read(folder/'manifest.json')
        for item in manifest['files']:
            assert sha(folder/item['path']) == item['sha256'], str(folder/item['path'])
        history[folder.name] = len(manifest['files'])
    assert len(history) == 20 and history['v0.16.0'] == 248, history
    media = {name: checked_source(name) for name in ['A', 'B']}
    video = ROOT/'references/raw/A_context_360p.mp4'
    assert sha(video) == 'dd70edb21517ce5867d1207c67a47b80ceb91a5c927be3ddead1178181c417f4'
    convolution = read(OUT/'independent_convolution.json')
    assert convolution['result'] == 'pass' and convolution['independent_convolution_comparisons'] == 42
    assert convolution['primary_results_sha256'] == sha(OUT/'results.json')
    for rows in convolution['cases'].values():
        for row in rows.values():
            for bank in ['exhaust_left', 'exhaust_right']:
                assert row[bank]['maximum_absolute_convolution_error'] < 2e-7
                assert row[bank]['convolution_error_to_actual_db'] < -115
    browser = read(OUT/'browser_qa.json')
    assert browser['result'] == 'pass' and browser['metadata_loads'] == 40
    assert browser['reference_metadata_loads'] == 2 and browser['reference_playback_mutual_exclusion']
    assert browser['position_preserved'] and browser['muted_playback_switch_preserved']
    assert not browser['mobile_horizontal_overflow'] and not browser['javascript_errors']
    ctest = (OUT/'ctest.txt').read_text(encoding='utf-8')
    assert '100% tests passed out of 1' in ctest
    assert '1/1 Test #1: causal_exhaust_phase_contracts ...   Passed' in ctest
    page = (ROOT/'research/主排气相位成形试听V1.html').read_text(encoding='utf-8')
    assert page.count('<audio data-reference') == 2
    assert (ROOT/'research/主排气相位成形实验V1.md').is_file()
    paths = [
        'tools/render_exhaust_phase.py', 'tools/analyze_exhaust_phase.py', 'tools/verify_exhaust_phase.py',
        'tools/runtime_review.py', 'tools/review_pairs.py', 'tools/reference_segments.py',
        'tools/comparison_page.py', 'tools/verify_review_player.cjs', 'references/segments_v1.json',
        'research/主排气相位成形实验V1.md', 'research/主排气相位成形试听V1.html',
        'research/goal_progress_exhaust_phase_v1.json', 'README.md',
        'build-experiment-exhaust-phase/phase_engine.c', 'build-experiment-exhaust-phase/phase_take.c',
        'build-experiment-exhaust-phase/Release/exhaust_phase_probe.exe',
        'build-experiment-exhaust-phase/Release/exhaust_phase_checks.exe',
        'build-experiment-exhaust-phase/Release/exhaust_phase.lib', 'build-v016/Release/vsl_core.lib']
    paths += [str(p.relative_to(ROOT)).replace('\\', '/')
              for p in sorted((ROOT/'experiments/exhaust_phase_v1').iterdir()) if p.is_file()]
    report = dict(result='pass', experiment='exhaust_phase_v1', native_runtime='0.16.0 unchanged',
                  primary_results_sha256=sha(OUT/'results.json'),
                  independent_convolution_sha256=sha(OUT/'independent_convolution.json'),
                  browser_qa_sha256=sha(OUT/'browser_qa.json'), ctest_sha256=sha(OUT/'ctest.txt'),
                  native_source_and_contract_files_unchanged=source_count,
                  native_binaries_unchanged=native['binaries'],
                  original_v011_files_unchanged={name: sha(ROOT/name) for name in v011},
                  preserved_snapshots=history, approved_media=media, reference_video_sha256=sha(video),
                  source_and_build_files={name: sha(ROOT/name) for name in paths},
                  artifacts={p.name: sha(p) for p in sorted(OUT.iterdir()) if p.is_file()},
                  scope='Implementation/preservation verification only. No subjective realism, new stochastic detail, bank width or measured target acoustic transfer inferred. Full goal remains active.')
    (OUT/'verification.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    SNAP.mkdir()
    for name in paths:
        target = SNAP/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/name, target)
    # Keep the audition package and numerical evidence together; full float
    # mixes and ten-source sets stay at their hash-bound existing render paths.
    copied = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and (path.suffix in ['.json', '.txt', '.png'] or
                               path.name.startswith(('audition_', 'reference_', 'impulse_'))):
            target = SNAP/'renders/exhaust_phase_v1'/path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            copied.append(path.name)
    files = [dict(path=str(p.relative_to(SNAP)).replace('\\', '/'), sha256=sha(p))
             for p in sorted(SNAP.rglob('*')) if p.is_file()]
    manifest = dict(experiment='exhaust_phase_v1', base_runtime='0.16.0 unchanged', files=files,
                    base_source_manifest_sha256=sha(ROOT/'baselines/v0.16.0/manifest.json'),
                    full_render_inventory_sha256=sha(OUT/'results.json'),
                    storage='Auditions, references, C impulses, sources, linked library, probes and audits included. Full float mixes/stems retained at original hash-bound render paths.',
                    status='Frozen unaccepted causal phase experiment; no subjective improvement inferred.')
    (SNAP/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    for item in files:
        assert sha(SNAP/item['path']) == item['sha256'], item['path']
    print(json.dumps(dict(result='pass', snapshot_files=len(files), preserved_snapshots=len(history),
                          native_source_files_unchanged=source_count,
                          convolution_comparisons=42, browser_audio_loads=42,
                          frozen_render_artifacts=len(copied)), indent=2))


if __name__ == '__main__':
    main()
