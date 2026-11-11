"""Actual path controls, frozen bypass, unchanged sources, native and browser QA."""
import json
from html.parser import HTMLParser
from runtime_review import ROOT, sha
from review_audit import read_json as read, pair, device, frozen_baselines
from reference_segments import checked_source
import soundfile as sf

OUT = ROOT/'renders/v0.14.0'
COUNTS = {f'v0.{v}.0':n for v,n in [(1,23),(2,64),(3,81),(4,99),(5,112),(6,161),
    (7,157),(8,182),(9,190),(10,205),(11,189),(12,156),(13,167)]}


def progress():
    full = read(ROOT/'research/goal_progress_v013.json')['full_objective_audit']
    full[2].update(status='Partial: canonical segments, context labels and robust relative fall in one selected rev; physical order/RPM/neutral/pedal remain unidentified.',
        evidence='research/驻车补油落转观测V1.md; references/analysis/rev_descent_v1/results.json')
    full[3].update(status='Partial: optional source-distance, per-ear time/engineering head shadow for stereo; listener-centre propagation for 7.1.4. Ten source stems and full driving logs unchanged. Actual HRTF/room/array listening and perceived realism unverified.',
        evidence='research/V014直达声传播.md; renders/v0.14.0/propagation_probe.json; renders/v0.14.0/verification.json')
    result = dict(goal_status='active', review_version='0.14.0', previous_goal_turn_classification='progress', this_goal_turn_classification='progress',
        implemented_this_iteration=['Rechecked unchanged V6 HEAD and audited existing direct sound routing',
            'Modular optional distance/time/head-shadow listener paths after unchanged source generation',
            '25-tap table-interpolated fractional path; common 13-sample algorithmic latency separate from geometry',
            '16 passing CTests; actual C impulse/frequency probes and supported-rate/near-distance controls',
            'Six common-gain listening pairs; exact frozen bypass across six scenes and five templates',
            'Ten pre-spatial sources/full drive CSV unchanged across bypass/stereo/7.1.4; actual native/UI/device/browser checks'],
        subjective_review='Optional default-off listener experiment. V011 timbre and V013/V014 listening remain unaccepted; no perceptual improvement inferred.',
        evidence=dict(review='research/V014试听.html', implementation='research/V014直达声传播.md', audit='renders/v0.14.0/workspace_audit.json'),
        full_objective_audit=full,
        remaining_work=['Independent physical order/RPM and operating-state evidence before fitting neutral loss/inertia',
            'Subjective comparison and measured listener/room/car acoustic transfer; generic ear model is not an identified vehicle field',
            'Reference RPM/load/state spectra, intake/exhaust transfer, weak high-order components and pressure/body coupling',
            'Identified per-car dynamics, lifecycle coupling, full multi-shaft DCT, tyre slip/ABS and thermal clutch response',
            'Calibrated stereo and physical 7.1.4 array listening'])
    (ROOT/'research/goal_progress_v014.json').write_text(json.dumps(result, indent=2), encoding='utf-8')


def main():
    r = read(OUT/'verification.json')
    assert r['version'] == '0.14.0' and r['seed'] == 48271 and not r['default_propagation']
    for name, digest in r['files'].items():
        assert sha(OUT/name) == digest, name
    for name, digest in r['binaries'].items():
        assert sha(ROOT/'build-v014/Release'/name) == digest, name
    auditions = {}
    assert len(r['cases']) == 6
    for name, takes in r['cases'].items():
        assert (OUT/f'{name}_frozen_v013.wav').read_bytes() == (OUT/f'{name}_legacy.wav').read_bytes()
        assert (OUT/f'{name}_legacy.wav').read_bytes() != (OUT/f'{name}_propagation.wav').read_bytes()
        auditions.update(pair(OUT, {tag:takes[tag]['audition'] for tag in ['legacy','propagation']},
            ['legacy','propagation'], raw={tag:OUT/f'{name}_{tag}.wav' for tag in ['legacy','propagation']}))
    assert len(r['legacy_template_checks']) == 5
    for number, digest in r['legacy_template_checks'].items():
        assert sha(OUT/f'legacy_profile_{number}_v014.wav') == sha(OUT/f'legacy_profile_{number}_v013.wav') == digest
    for name in ['drive_legacy.csv','drive_propagation.csv','drive_714.csv']:
        assert (OUT/name).read_bytes() == (ROOT/'renders/v0.13.0/drive_v013.csv').read_bytes()
    scene = read(OUT/'drive_714_scene.json')
    assert scene['direct_propagation']['enabled'] and scene['parameters']['propagation'] == 1
    assert scene['propagation_filter'] == dict(taps=25, phases=256, algorithmic_latency_samples=13,
        type='table-interpolated Blackman sinc; common FIR latency is separate from acoustic distance')
    assert scene['channels'] == ['FL','FR','FC','LFE','BL','BR','SL','SR','TFL','TFR','TBL','TBR']
    for obj in scene['objects']:
        baseline = ROOT/f'renders/v0.13.0/stems/drive_v013_{obj["name"]}.wav'
        assert sf.info(baseline).subtype == 'FLOAT'
        for path in [OUT/obj['file'], OUT/f'stems/drive_legacy_{obj["name"]}.wav', OUT/f'stems/drive_propagation_{obj["name"]}.wav']:
            assert path.read_bytes() == baseline.read_bytes()
        assert sha(OUT/obj['file']) == obj['sha256']
    assert len(scene['objects']) == 10
    assert (OUT/'ctest.log').read_bytes().count(b'Test Passed.') == 16
    assert b'geometric_direct_propagation' in (OUT/'ctest.log').read_bytes()
    device(r['device'], '0.14.0');assert r['device'] == read(OUT/'ui_smoke.json')
    for key in ['propagation_control','propagation_preset_roundtrip','legacy_preset_retains_spatial_renderer','propagation_active_on_device']:
        assert r['device'][key]
    browser = read(OUT/'browser_qa.json');assert browser['result'] == 'pass' and browser['metadata_loads'] == 12
    probe = read(OUT/'propagation_probe.json');assert probe['status'] == 'pass'
    assert probe['compiled_probe_sha256'] == r['binaries']['vsl_spatial_probe.exe']
    for group in ['rate_controls','fractional_controls']:
        for control in probe[group].values():
            for name, digest in control['files'].items():
                assert sha(OUT/'propagation'/name) == digest
            assert control['centre_filter_max_abs_magnitude_error_db'] < .3
            assert control['centre_filter_max_abs_phase_error_deg'] < 1
    assert len(probe['rate_controls']) == 3 and len(probe['fractional_controls']) == 17
    # Source/vehicle algorithms are untouched apart from engine routing hooks,
    # the new selector and init. Check actual files rather than infer from tests.
    for folder in ['drive','core','profiles']:
        for path in (ROOT/'src'/folder).iterdir():
            relative = path.relative_to(ROOT)
            allowed = {'src/core/types.h','src/core/engine.c','src/core/engine.h',
                'src/core/profiles.c','src/profiles/propagation.c','src/profiles/propagation.h'}
            if str(relative).replace('\\','/') in allowed or not path.is_file():
                continue
            assert sha(path) == sha(ROOT/'baselines/v0.13.0'/relative), relative
    upstream = read(ROOT/'research/upstream_head_v014.json')
    assert upstream['sha'] == 'ac2b37d8639027d79934a2023cf8d1d37d3b2f96'
    assert sha(ROOT/'research/upstream_v6/code/drive_model.js') == upstream['snapshot_sha256']
    class Links(HTMLParser):
        def handle_starttag(self, tag, attrs):
            for key, value in attrs:
                if key in ['src','href'] and not value.startswith(('http:','https:','#')):
                    assert (ROOT/'research'/value).resolve().is_file(), value
    Links().feed((ROOT/'research/V014试听.html').read_text(encoding='utf-8'))
    history = frozen_baselines(COUNTS)
    media = {name:checked_source(name) for name in ['A','B']}
    progress()
    sources = [ROOT/'CMakeLists.txt', *(ROOT/'src').rglob('*.c'), *(ROOT/'src').rglob('*.h'), *(ROOT/'tests').glob('*.c')]
    deliverables = ['README.md','AGENTS.md','Launch.cmd','build.ps1','references/segments_v1.json',
        'research/V014试听.html','research/V014直达声传播.md','research/upstream_head_v014.json','research/goal_progress_v014.json']
    deliverables += ['tools/'+name for name in ['analyze_propagation.py','render_v014_review.py','make_v014_review.py',
        'verify_v014.py','freeze_v014.py','runtime_review.py','review_audit.py','review_pairs.py','comparison_page.py',
        'verify_review_player.cjs','reference_segments.py','freeze_review.py']]
    audit = dict(result='pass', version='0.14.0', ctest_count=16, shared_gain_pairs=6,
        legacy_template_checks=5, unchanged_scene_checks=6, unchanged_source_count=10, unchanged_full_drive_trace=True,
        approved_media=media, preserved_baselines=history, audition_files=auditions,
        source_code={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(sources)},
        deliverables={name:sha(ROOT/name) for name in deliverables},
        rendered_artifacts={str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name != 'workspace_audit.json'},
        goal_status='active; optional listener paths verified in software, subjective timbre/car identification/full driving and actual array validation incomplete')
    (OUT/'workspace_audit.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    print(json.dumps(dict(result='pass', version='0.14.0', tests=16, pairs=6, history=history, source_count=10, goal='active'), indent=2))


if __name__ == '__main__':
    main()
