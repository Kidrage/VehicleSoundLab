"""Freeze checked observations without changing any native baseline."""
import json
import shutil
from runtime_review import ROOT, sha
from reference_segments import checked_source


def main():
    out = ROOT/'baselines/repeat_shape_v1'
    if out.exists():
        raise SystemExit('Preserve completed repeat_shape_v1.')
    source = ROOT/'references/analysis/repeat_shape_v1'
    result = json.loads((source/'results.json').read_text(encoding='utf-8'))
    verification = json.loads((source/'verification.json').read_text(encoding='utf-8'))
    assert verification['result'] == 'pass'
    assert sha(source/'results.json') == verification['results_sha256']
    for name, digest in result['files'].items():
        assert sha(source/name) == digest, name
    for group in [result['tools'], verification['tools'], result['native_preserved'], result['exploration']['files']]:
        for name, digest in group.items():
            assert sha(ROOT/name) == digest, name
    assert sha(ROOT/'baselines/v0.19.0/manifest.json') == result['native_manifest_sha256']
    assert sha(ROOT/result['tracks']['path']) == result['tracks']['sha256']
    assert sha(ROOT/result['tracks']['frozen_manifest']) == result['tracks']['frozen_manifest_sha256']
    checked_source('A')
    names = ['README.md', 'references/segments_v1.json',
        'research/重复补油同谱线声形核查V1.md', 'research/goal_progress_repeat_shape_v1.json',
        'tools/runtime_review.py', 'tools/reference_segments.py', 'tools/spectral_coordinates.py',
        'tools/matched_shapes.py', 'tools/analyze_repeat_shape.py', 'tools/verify_repeat_shape.py',
        'tools/freeze_repeat_shape.py', 'src/profiles/voicing.c', 'src/core/orchestrator.c',
        'src/core/exhaust_spectrum.c', result['tracks']['path']]
    names += [p.relative_to(ROOT).as_posix() for p in source.iterdir() if p.is_file()]
    names += list(result['exploration']['files'])
    identities = {p.parent.name:sha(p) for p in sorted((ROOT/'baselines').glob('*/manifest.json'))}
    assert len(identities) == 35
    out.mkdir()
    for name in sorted(set(names)):
        target = out/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/name, target)
    files = [dict(path=p.relative_to(out).as_posix(), sha256=sha(p))
        for p in sorted(out.rglob('*')) if p.is_file()]
    manifest = dict(study='repeat_shape_v1', runtime='0.19.0 unchanged', seed=48271,
        status='Observed repeated mixed exterior descents; no target-car calibration or subjective acceptance. Broad goal active.',
        original_media='Approved raw/float stereo remains at workspace catalog paths, not duplicated here.',
        native_manifest_sha256=result['native_manifest_sha256'], previous_snapshot_manifest_identities=identities,
        files=files)
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    for item in files:
        assert sha(out/item['path']) == item['sha256']
    print(f'Frozen repeat_shape_v1: {len(files)} files verified; nativeV019 preserved. Broad goal active.')


if __name__ == '__main__':
    main()
