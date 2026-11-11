"""Optional geometric listener paths; exact legacy and unchanged sources."""
import json
import shutil
from runtime_review import ROOT, render, sha, smoke, scene_paths
from review_pairs import common_pair

OUT = ROOT/'renders/v0.14.0'
OLD = ROOT/'baselines/v0.13.0/bin/vsl_render.exe'
NEW = ROOT/'build-v014/Release/vsl_render.exe'
CASES = {
    'idle': ['--rpm', '1200', '--load', '.18', '--seconds', '4.2', '--width', '1', '--space', '0'],
    'mid': ['--rpm', '4000', '--load', '.65', '--seconds', '4.2', '--width', '1', '--space', '0'],
    'high': ['--rpm', '8000', '--load', '.85', '--seconds', '4.2', '--width', '1', '--space', '0'],
    'drive': ['--scenario', 'auto', '--seconds', '30', '--width', '.8'],
    'cabin': ['--rpm', '4000', '--load', '.65', '--seconds', '4.2', '--width', '.8', '--cabin'],
    'imported': ['--rpm', '4000', '--load', '.65', '--seconds', '4.2', '--width', '1', '--space', '0',
        '--dna', str(ROOT/'renders/v0.9.0/dna_check/known_steady_harmonics.dna')],
}


def main():
    destination = OUT/'verification.json'
    if destination.exists():
        raise SystemExit('Preserve completed V014 review.')
    OUT.mkdir(parents=True, exist_ok=True);(OUT/'stems').mkdir(exist_ok=True)
    result = dict(version='0.14.0', seed=48271, default_propagation=False, cases={}, legacy_template_checks={})
    for name, args in CASES.items():
        arrays = [];takes = {}
        frozen = OUT/f'{name}_frozen_v013.wav'
        render(OLD, frozen, args, '0.13.0')
        for method, option in [('legacy', '0'), ('propagation', '1')]:
            extra = ['--propagation', option]
            if name == 'drive':
                extra += ['--trace', str(OUT/f'drive_{method}.csv'), '--stems', str(OUT/f'stems/drive_{method}')]
            x, info = render(NEW, OUT/f'{name}_{method}.wav', args, '0.14.0', extra)
            arrays.append(x);takes[method] = info
        assert frozen.read_bytes() == (OUT/f'{name}_legacy.wav').read_bytes(), name
        assert (OUT/f'{name}_propagation.wav').read_bytes() != frozen.read_bytes(), name
        auditions = common_pair(OUT, arrays, ['legacy', 'propagation'], name)
        for method in takes:
            takes[method]['audition'] = auditions[method]
        result['cases'][name] = takes
        print('review', name, flush=True)
    assert (OUT/'drive_legacy.csv').read_bytes() == (OUT/'drive_propagation.csv').read_bytes()
    # A frozen driving run with the same inputs already exists.
    assert (OUT/'drive_legacy.csv').read_bytes() == (ROOT/'renders/v0.13.0/drive_v013.csv').read_bytes()
    for profile in range(5):
        args = ['--profile', str(profile), '--rpm', '4000', '--load', '.65', '--seconds', '3']
        files = [OUT/f'legacy_profile_{profile}_{tag}.wav' for tag in ['v013', 'v014']]
        for exe, path, version in [(OLD, files[0], '0.13.0'), (NEW, files[1], '0.14.0')]:
            render(exe, path, args, version)
        assert files[0].read_bytes() == files[1].read_bytes(), profile
        result['legacy_template_checks'][str(profile)] = sha(files[1])
    _, result['bed714'] = render(NEW, OUT/'drive_714.wav', CASES['drive']+['--propagation', '1', '--channels', '12'],
        '0.14.0', ['--stems', str(OUT/'stems/drive_714'), '--scene', str(OUT/'drive_714_scene.json'), '--trace', str(OUT/'drive_714.csv')])
    scene_paths(OUT/'drive_714_scene.json', OUT)
    assert (OUT/'drive_714.csv').read_bytes() == (OUT/'drive_legacy.csv').read_bytes()
    for obj in json.loads((OUT/'drive_714_scene.json').read_text())['objects']:
        reference = OUT/f'stems/drive_legacy_{obj["name"]}.wav'
        assert reference.read_bytes() == (OUT/f'stems/drive_propagation_{obj["name"]}.wav').read_bytes()
        assert reference.read_bytes() == (OUT/obj['file']).read_bytes()
        assert reference.read_bytes() == (ROOT/f'renders/v0.13.0/stems/drive_v013_{obj["name"]}.wav').read_bytes()
    result['unchanged_source_count'] = 10
    result['device'] = smoke(ROOT/'build-v014', OUT, '0.14.0')
    for key in ['propagation_control', 'propagation_preset_roundtrip', 'legacy_preset_retains_spatial_renderer', 'propagation_active_on_device']:
        assert result['device'][key], key
    for name in ['ui_control_roundtrip.ini', 'ui_legacy_preset.ini', 'ui_v08_preset.ini', 'ui_v013_preset.ini']:
        shutil.copy2(ROOT/'renders'/name, OUT/name)
    shutil.copy2(ROOT/'build-v014/Testing/Temporary/LastTest.log', OUT/'ctest.log')
    assert (OUT/'ctest.log').read_bytes().count(b'Test Passed.') == 16
    result['binaries'] = {name:sha(ROOT/'build-v014/Release'/name) for name in ['VehicleSoundLab.exe', 'vsl_render.exe', 'vsl_spatial_probe.exe']}
    result['files'] = {str(p.relative_to(OUT)).replace('\\', '/'):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
    destination.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result['device'], indent=2))


if __name__ == '__main__':
    main()
