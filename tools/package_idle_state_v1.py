"""Index, freeze and verify the optional fixed-idle source/state experiment."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct
import subprocess
import zipfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--stage', choices=['index', 'freeze', 'verify'], required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
analysis = a.workspace / 'references/analysis/idle_state_v1'
root = a.workspace / 'baselines/idle_state_v1'
modified = {'modules/atlas_drive/render.c', 'modules/atlas_drive/render.h',
            'modules/atlas_take/assets.c'}


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                    encoding='utf-8', newline='\n')


def wave_chunks(path):
    data = path.read_bytes()
    assert data[:4] == b'RIFF' and data[8:12] == b'WAVE'
    assert struct.unpack_from('<I', data, 4)[0] + 8 == len(data)
    chunks, offset = {}, 12
    while offset < len(data):
        name, size = struct.unpack_from('<4sI', data, offset)
        assert name not in chunks and offset + 8 + size <= len(data)
        chunks[name] = data[offset + 8:offset + 8 + size]
        offset += 8 + size + (size % 2)
    assert offset == len(data)
    return chunks


parent_summary = load(repo / 'research/accel_material_v1_summary.json')
parent = a.workspace / parent_summary['freeze']
assert sha(parent / 'manifest.json') == parent_summary['manifest_sha256']
old_c = load(parent / 'C_files_sha256.json')
voices = load(parent / 'voice_files_sha256.json')
assert len(old_c) == 550 and len(voices) == 67
assert {name for name, digest in old_c.items() if sha(repo / name) != digest} == modified
assert all(sha(repo / name) == digest for name, digest in voices.items())
new = set()
for folder in ['modules/modal_layer', 'experiments/idle_state_v1', 'modules/atlas_drive']:
    new.update(path.relative_to(repo).as_posix() for path in (repo / folder).glob('*')
               if path.suffix.lower() in ('.c', '.h') and path.is_file())
new -= set(old_c)
assert len(new) == 12
current_c = {name: sha(repo / name) for name in sorted(set(old_c) | new)}


def index_rows():
    path = repo / 'handoff/C文件索引.csv'
    rows = list(csv.reader(io.StringIO(path.read_text(encoding='utf-8-sig'))))
    assert all(len(row) == 5 for row in rows)
    return {row[0]: row for row in rows[1:]}


if a.stage == 'index':
    index = repo / 'handoff/C文件索引.csv'
    assert len(index_rows()) == 550
    lines = index.read_bytes().splitlines(keepends=True)
    for n, line in enumerate(lines[1:], 1):
        name = next(csv.reader([line.decode('utf-8-sig')]))[0]
        if name in modified:
            assert old_c[name].encode() in line
            lines[n] = line.replace(old_c[name].encode(), current_c[name].encode())
    prefix = b''.join(lines)
    assert prefix.endswith(b'\n')
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer, lineterminator='\n')
    for name in sorted(new):
        if name.startswith('modules/modal_layer/'):
            module, target, job = '独立持续声源', 'modal_layer', '借用参数校验／持续OSC与共振／有限过渡'
        elif name.startswith('modules/atlas_drive/'):
            module, target, job = '空间前声源接口', 'atlas_drive', '只读驾驶状态／分层处理／有限数值输出边界'
        else:
            module, target, job = '怠速状态实验', 'idle_state_v1', 'F2工况适配／已知核与集成检查／分轨与状态导出'
        writer.writerow([name, module, target, job, current_c[name]])
    index.write_bytes(prefix + buffer.getvalue().encode('utf-8'))
    rows = index_rows()
    assert len(rows) == 562
    assert all(rows[name][4] == digest for name, digest in current_c.items())
    print(json.dumps(dict(result='indexed', total=562, unchanged=547, modified=3, added=12)))
    raise SystemExit


if a.stage == 'freeze':
    reports = {name: load(analysis / name / 'report.json') for name in
               ['kernel1', 'kernel2', 'kernel3', 'full1', 'render1', 'level1',
                'full2', 'render2', 'review1', 'review2', 'preview_check1', 'preview_check2', 'package1']}
    assert all(reports[name]['result'] == 'failed' for name in ['kernel1', 'kernel2', 'preview_check1', 'package1'])
    assert reports['full2']['result'] == 'passed' and reports['full2']['tests'] == 57
    for name, digest in reports['full2']['sources'].items():
        assert sha(repo / name) == sha(analysis / 'full2/exact_sources' / name) == digest
    rendered = reports['render2']
    assert rendered['result'] == 'continuous_idle_state_and_all84_legacy_WAVs_verified'
    assert sum(row['WAV_bytes_exact'] for row in rendered['legacy']) == 84
    assert all(row['controller_trace_exact'] for row in rendered['legacy'])
    assert rendered['entire_controller_and_envelope_trace_exact']
    assert rendered['build_proof_sha256'] == sha(analysis / 'full2/report.json')
    assert rendered['level_proof_sha256'] == sha(analysis / 'level1/report.json')
    assert rendered['source_sha256'] == sha(repo / 'tools/render_idle_state_v1.py')
    level = reports['level1']
    assert level['result'] == 'one_fixed_monitoring_trim_derived'
    assert sha(repo / 'experiments/idle_state_v1/study.h') == level['generated_header_sha256']
    assert sha(analysis / 'level1/study.h') == level['generated_header_sha256']
    assert reports['preview_check2']['result'] == 'preview_controls_trace_and_muted_browser_playback_verified'
    # libsndfile's FLOAT PEAK timestamp may change; check actual data separately.
    for name in ['original.wav', 'candidate.wav', 'state.json']:
        assert sha(analysis / 'review1' / name) == sha(analysis / 'review2' / name)
    solo1 = wave_chunks(analysis / 'review1/idle_solo.wav')
    solo2 = wave_chunks(analysis / 'review2/idle_solo.wav')
    assert solo1.keys() == solo2.keys()
    assert solo1[b'fmt '] == solo2[b'fmt '] and solo1[b'data'] == solo2[b'data']
    assert solo1[b'PEAK'][:4] == solo2[b'PEAK'][:4] and solo1[b'PEAK'][8:] == solo2[b'PEAK'][8:]
    assert all(solo1[key] == solo2[key] for key in solo1 if key != b'PEAK')
    for name, digest in reports['review2']['files'].items():
        assert sha(analysis / 'review2' / name) == digest
    rows = index_rows()
    assert len(rows) == 562 and all(rows[name][4] == digest for name, digest in current_c.items())
    # F2 experimental assets are separate from the 67 runtime voice profiles.
    f2 = ['experiments/modal_idle_v1/F2_fixed_idle.msource',
          'experiments/modal_idle_v1/F2_fixed_idle.rdetail']
    f2_hashes = {name: sha(repo / name) for name in f2}
    for name, digest in f2_hashes.items():
        tracked = subprocess.check_output(['git', 'show', 'HEAD:' + name], cwd=repo)
        assert hashlib.sha256(tracked).hexdigest() == digest
    root.mkdir(parents=True, exist_ok=False)
    shutil.copytree(analysis, root / 'evidence')
    paths = set(reports['full2']['sources']) | set(current_c) | set(voices) | set(f2)
    paths.update([
        'tools/package_idle_state_v1.py', 'tools/render_idle_state_v1.py',
        'tools/review_idle_state_v1.py', 'tools/calibrate_idle_state_level_v1.py',
        'tools/check_idle_state_preview.cjs', 'research/idle_state_level_v1_plan.json',
        'research/怠速状态衔接V1.md', 'research/怠速素材与独立声线V1.md',
        'research/独立怠速声源C移植V1.md', 'research/accel_material_v1_summary.json',
        'research/idle_modal_c_v1_summary.json', 'modules/modal_layer/README.md',
        'modules/atlas_drive/README.md', 'handoff/C文件索引.csv',
        'handoff/C模块与接口.md', 'handoff/算法说明.md', 'handoff/研究续接.md',
        'handoff/开发留痕.md', 'AGENTS.md'])
    for name in sorted(paths):
        dest = root / 'source' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / name, dest)
    with zipfile.ZipFile(root / 'source.zip', 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((root / 'source').rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(root / 'source').as_posix())
    save(root / 'C_files_sha256.json', current_c)
    save(root / 'voice_files_sha256.json', voices)
    validation = dict(schema='vsl.idle-state-freeze/1',
        result='optional_fixed_idle_state_integration_verified_timbre_pending',
        parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
        parent_freeze=parent_summary['freeze'], parent_manifest_sha256=parent_summary['manifest_sha256'],
        C_H=dict(total=562, unchanged=547, modified=sorted(modified), added=sorted(new)),
        voices_unchanged=67, F2_assets_unchanged=f2_hashes,
        CTest_count=57, legacy_WAV_byte_exact=84, legacy_controller_CSV_byte_exact=3,
        entire_controller_and_envelope_trace_exact=True,
        ramp_maximum_error=max(row['ramp_maximum_error'] for row in rendered['generated']),
        added_maximum_FS_error=max(row['added_maximum_FS_error'] for row in rendered['generated']),
        level_gain=level['level_gain'], fixed_level_fit_and_unfit_check=level['holds'],
        original_failed_builds_preview_and_container_check_retained=True,
        browser_controls_and_muted_playback=True, browser_layout_visually_reviewed=True,
        review_mix_containers_and_all_audio_samples_unchanged=True,
        solo_container_difference='PEAK timestamp only; fmt/data/all other chunks exact',
        source_timbre_refitted=False,
        timbre_acceptance=False, original_F2_timbre_question='pending',
        native_UI_or_default_changed=False, schema8_supports_processor=False,
        physical_7_1_4_or_native_device_verified=False, actual_F2_RPM_calibrated=False,
        contexts='F2 LP610 tailpipe vs A Performante; engineering crossfade, not same-car reconstruction',
        reports={name: sha(analysis / name / 'report.json') for name in reports})
    save(root / 'validation.json', validation)
    entries = [dict(path=path.relative_to(root).as_posix(), bytes=path.stat().st_size, sha256=sha(path))
               for path in sorted(root.rglob('*')) if path.is_file()]
    manifest = dict(files=entries, file_count=len(entries), bytes=sum(row['bytes'] for row in entries))
    save(root / 'manifest.json', manifest)
    digest = sha(root / 'manifest.json')
    save(repo / 'research/idle_state_v1_summary.json', dict(validation,
        freeze='baselines/idle_state_v1', manifest_sha256=digest,
        file_count=len(entries), bytes=manifest['bytes']))
    index = repo / 'handoff/阶段索引.csv'
    prefix = index.read_bytes()
    assert b'\nidle_state_v1,' not in prefix
    row = ['idle_state_v1', 'baselines/idle_state_v1/manifest.json', str(len(entries)), digest,
        'Optional pre-spatial fixed-F2 source, one driver;57CTest/84oldWAV exact; fixed monitoring trim. Initial build and browser seek failures retained',
        'Timbre pending; no F2 RPM calibration/native UI/default/schema8 adoption;562C-H indexed/67voices unchanged',
        'research/怠速状态衔接V1.md | research/idle_state_v1_summary.json',
        'baselines/idle_state_v1/validation.json | baselines/idle_state_v1/evidence/full2/report.json | baselines/idle_state_v1/evidence/render2/report.json']
    buffer = io.StringIO(newline='')
    csv.writer(buffer, lineterminator='\n').writerow(row)
    index.write_bytes(prefix + (b'' if prefix.endswith(b'\n') else b'\n') + buffer.getvalue().encode('utf-8'))
    assert index.read_bytes().startswith(prefix)
    print(json.dumps(dict(stage='frozen', files=len(entries), bytes=manifest['bytes'], manifest_sha256=digest)))
else:
    manifest = load(root / 'manifest.json')
    for row in manifest['files']:
        path = root / row['path']
        assert path.stat().st_size == row['bytes'] and sha(path) == row['sha256']
    assert load(root / 'C_files_sha256.json') == current_c
    assert load(root / 'voice_files_sha256.json') == voices
    summary = load(repo / 'research/idle_state_v1_summary.json')
    assert sha(root / 'manifest.json') == summary['manifest_sha256']
    rows = list(csv.reader(io.StringIO((repo / 'handoff/阶段索引.csv').read_text(encoding='utf-8-sig'))))
    assert all(len(row) == 8 for row in rows)
    assert rows[-1][0] == 'idle_state_v1' and rows[-1][3] == summary['manifest_sha256']
    index = index_rows()
    assert len(index) == 562 and all(index[name][4] == digest for name, digest in current_c.items())
    assert all(sha(repo / name) == sha(root / 'source' / name)
               for name in [*current_c, *voices, 'tools/package_idle_state_v1.py'])
    print(json.dumps(dict(stage='verified', files=manifest['file_count'], bytes=manifest['bytes'])))
