"""Freeze phase-free source observations and their unsuccessful first audit."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--stage', choices=['freeze', 'verify'], required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
root = a.workspace / 'baselines/accel_material_v1'
analysis = a.workspace / 'references/analysis/accel_material_v1'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')


if a.stage == 'freeze':
    observed = load(analysis / 'observe1/report.json')
    failed = load(analysis / 'audit1/report.json')
    audited = load(analysis / 'audit2/report.json')
    assert observed['result'] == 'fixed_native_acceleration_observations_complete_not_a_synthesis_profile'
    assert failed['result'] == 'failed'
    assert audited['result'] == 'all48_native_tiles_and_all7728_scores_independently_verified'
    assert sum(len(x['tiles']) for x in observed['observations']) == 48
    assert load(analysis / 'review1/report.json')['result'] == 'saved_observations_plotted_without_refit'
    parent_summary = load(repo / 'research/idle_modal_c_v1_summary.json')
    parent = a.workspace / parent_summary['freeze']
    assert sha(parent / 'manifest.json') == parent_summary['manifest_sha256']
    original_c = load(parent / 'C_files_sha256.json')
    original_voices = load(parent / 'voice_files_sha256.json')
    assert len(original_c) == 550 and len(original_voices) == 67
    for entries in [original_c, original_voices]:
        assert all(sha(repo / name) == digest for name, digest in entries.items())
    for name, digest in observed['sources'].items():
        assert sha(repo / name) == sha(analysis / 'observe1/exact_sources' / name) == digest
    assert sha(repo / 'tools/audit_accel_material_v1.py') == audited['source_sha256']
    root.mkdir(parents=True, exist_ok=False)
    # Retain every source snapshot, array, plot and failure, not just summaries.
    shutil.copytree(analysis, root / 'evidence')
    source_paths = {repo / name for name in observed['sources']}
    source_paths.update([Path(__file__), repo / 'tools/audit_accel_material_v1.py',
        repo / 'tools/plot_accel_material_v1.py', repo / 'research/加速素材音高与谱形V1.md',
        repo / 'research/state_media_v1_visual_review.json', repo / 'research/F_state_audition_v1_review.json',
        repo / 'research/F_state_evidence_v1_summary.json', repo / 'research/F3加速音轨复用核查V1.md',
        repo / 'references/segments_v1.json', repo / 'handoff/研究续接.md',
        repo / 'handoff/开发留痕.md', repo / 'AGENTS.md'])
    for path in sorted(source_paths):
        destination = root / 'source' / path.relative_to(repo)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    with zipfile.ZipFile(root / 'source.zip', 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((root / 'source').rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(root / 'source').as_posix())
    save(root / 'C_files_sha256.json', original_c)
    save(root / 'voice_files_sha256.json', original_voices)
    validation = dict(schema='vsl.acceleration-material-freeze/1',
        result='source_observations_verified_no_synthesis_adoption',
        parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
        parent_freeze=parent_summary['freeze'], parent_manifest_sha256=parent_summary['manifest_sha256'],
        source_catalog_sha256=sha(repo / 'references/segments_v1.json'),
        observations=[dict(segment=x['segment'], tiles=len(x['tiles']), supported=x['supported_tiles'],
            last_ratio=x['tiles'][-1]['spectral_scale']['ratio'],
            last_supported=x['tiles'][-1]['spectral_scale']['supported']) for x in observed['observations']],
        audit_maxima=audited['maxima'], first_audit_failure_retained=True,
        plot_visually_reviewed=True, shared_phase_or_RPM=False, independent_takes=False,
        timbre_acceptance=False, idle_listening='pending original F2 review2 question',
        C_H_unchanged=550, voices_unchanged=67,
        runtime_driver_UI_take_spatial_changed=False, old_CTest_repeated=False,
        reports={name:sha(analysis / name / 'report.json') for name in ['observe1','audit1','audit2','review1']})
    save(root / 'validation.json', validation)
    entries = [dict(path=path.relative_to(root).as_posix(), bytes=path.stat().st_size, sha256=sha(path))
               for path in sorted(root.rglob('*')) if path.is_file()]
    manifest = dict(files=entries, file_count=len(entries), bytes=sum(row['bytes'] for row in entries))
    save(root / 'manifest.json', manifest)
    digest = sha(root / 'manifest.json')
    save(repo / 'research/accel_material_v1_summary.json', dict(validation,
        freeze='baselines/accel_material_v1', manifest_sha256=digest,
        file_count=len(entries), bytes=manifest['bytes']))
    index = repo / 'handoff/阶段索引.csv'
    prefix = index.read_bytes()
    assert b'\naccel_material_v1,' not in prefix
    row = ['accel_material_v1', 'baselines/accel_material_v1/manifest.json', str(len(entries)), digest,
        'F3 all48native tiles/7728scores; relative spectral-scale and band-colour observations. First prefix-cancellation audit failure retained; fsum audit passes original gate. No synthesis profile',
        'F2 idle timbre pending; no RPM/load clock or independent takes;550C-H/67voices unchanged',
        'research/加速素材音高与谱形V1.md | research/accel_material_v1_summary.json',
        'baselines/accel_material_v1/validation.json | baselines/accel_material_v1/evidence/audit2/report.json']
    buffer = io.StringIO(newline='')
    csv.writer(buffer, lineterminator='\n').writerow(row)
    index.write_bytes(prefix + (b'' if prefix.endswith(b'\n') else b'\n') + buffer.getvalue().encode('utf-8'))
    assert index.read_bytes().startswith(prefix)
    print(json.dumps(dict(stage='frozen', files=len(entries), bytes=manifest['bytes'], manifest_sha256=digest)), flush=True)
else:
    manifest = load(root / 'manifest.json')
    for item in manifest['files']:
        path = root / item['path']
        assert path.stat().st_size == item['bytes'] and sha(path) == item['sha256']
    for file in ['C_files_sha256.json', 'voice_files_sha256.json']:
        assert all(sha(repo / name) == digest for name, digest in load(root / file).items())
    summary = load(repo / 'research/accel_material_v1_summary.json')
    assert summary['manifest_sha256'] == sha(root / 'manifest.json')
    rows = list(csv.reader(io.StringIO((repo / 'handoff/阶段索引.csv').read_text(encoding='utf-8-sig'))))
    assert all(len(row) == 8 for row in rows)
    assert rows[-1][0] == 'accel_material_v1' and rows[-1][3] == summary['manifest_sha256']
    print(json.dumps(dict(stage='verified', files=manifest['file_count'], bytes=manifest['bytes'])), flush=True)
