"""Bind unified CATCH integration to executed sources and freeze a clean commit."""
import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def index(path):
    with path.open(encoding='utf-8-sig') as stream:
        rows = list(csv.DictReader(stream))
    result = {row['文件']: row for row in rows}
    assert len(result) == len(rows), 'duplicate source index entry'
    return result


def file_hashes(root):
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts}


p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--freeze', action='store_true')
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
root = a.workspace / 'references/analysis/catch_drive_v1'
summary = repo / 'research/catch_drive_v1_summary.json'
docs = [
    'research/接火低频统一驾驶V1.md', 'research/catch_drive_v1_summary.json',
    'handoff/C文件索引.csv', 'handoff/C模块与接口.md', 'handoff/算法说明.md',
    'handoff/研究续接.md', 'handoff/开发留痕.md', 'README.md', 'AGENTS.md',
    'experiments/catch_drive_v1/README.md', 'modules/atlas_drive/README.md',
    'modules/atlas_take/README.md', 'modules/atlas_take_io/README.md',
    'modules/start_texture/README.md', 'modules/catch_bloom/README.md',
    'voices/catch_bloom_v1/README.md',
]

if a.freeze:
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip(), 'dirty checkout'
    r = read(summary)
    for name, digest in r['current_source_sha256'].items():
        assert sha(repo / name) == digest, name
    assert file_hashes(root) == r['evidence_sha256'], 'evidence changed'
    out = a.workspace / 'baselines/catch_drive_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(root, out / 'evidence', ignore=shutil.ignore_patterns('__pycache__'))
    for name in docs:
        dest = out / 'docs' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / name, dest)
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    subprocess.run(['git', 'archive', '--format=zip', '--output=' + str(out / 'source.zip'), revision],
                   cwd=repo, check=True)
    with zipfile.ZipFile(out / 'source.zip') as archive:
        assert archive.testzip() is None
    files = [dict(path=x.relative_to(out).as_posix(), bytes=x.stat().st_size, sha256=sha(x))
             for x in sorted(out.rglob('*')) if x.is_file()]
    manifest = dict(schema='vsl.catch-drive-freeze/1', source_commit=revision,
                    human_accepted=False, native_UI_integrated=True,
                    UI_interaction_checked=False, long_run_checked=False,
                    physical_12speakers_checked=False, files=files)
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
                                       encoding='utf-8', newline='\n')
    for row in files:
        assert sha(out / row['path']) == row['sha256'], row['path']
    print(json.dumps(dict(path=str(out), files=len(files), bytes=sum(x['bytes'] for x in files),
                          commit=revision)))
else:
    before = read(root / 'before/report.json')
    build = read(root / 'build2/report.json')
    failed_build = read(root / 'build1/report.json')
    verification = read(root / 'verification1/report.json')
    review = read(root / 'review1/report.json')
    native = read(root / 'native1/report.json')
    assert before['result'] == 'schema4_sources_and_players_preserved'
    assert build['result'] == 'build_and_45tests_pass'
    assert failed_build['result'] == 'failed' and all(x['exit_code'] == 0 for x in failed_build['commands'])
    assert verification['result'] == 'integrated_catch_function_pass'
    assert review['result'] == 'pass' and len(review['clips']) == 6
    for name, digest in build['source_sha256'].items():
        assert sha(repo / name) == digest, name
        assert sha(root / 'build2/exact_sources' / name) == digest, name
    for name, digest in verification['binaries'].items():
        assert sha(root / 'verification1/bin' / name) == digest, name
        assert sha(Path(build['build']) / 'bin/Release' / name) == digest, name
    assert native['binary_sha256'] == verification['binaries']['VslAtlasMonitor.exe']
    assert not native['UI_interaction_checked'] and not native['human_accepted']
    old = index(root / 'before/C文件索引.csv')
    now = index(repo / 'handoff/C文件索引.csv')
    assert len(old) == 466 and len(now) == 468 and set(old) <= set(now)
    changed = []
    for name, row in now.items():
        assert sha(repo / name) == row['SHA-256'], name
        if name in old:
            assert {k: v for k, v in old[name].items() if k != 'SHA-256'} == {
                k: v for k, v in row.items() if k != 'SHA-256'}, name
            if row['SHA-256'] != old[name]['SHA-256']:
                changed.append(name)
    assert len(changed) == 24 and not any(n.startswith(('src/', 'modules/catch_bloom/')) for n in changed)
    assert sorted(set(now) - set(old)) == [
        'experiments/catch_drive_v1/checks.c', 'experiments/catch_drive_v1/probe.c']
    accepted = read(repo / 'research/catch_bloom_v1_summary.json')['accepted_model_sha256']
    for name, digest in accepted.items():
        assert sha(repo / name) == digest, name
    assert sum(x['WAV_bytes_equal'] for x in verification['legacy']) == 108
    assert all(x['controls_bytes_equal'] for x in verification['legacy'])
    assert len(verification['scene']) == 6 and all(x['driver_trace_byte_equal'] for x in verification['scene'])
    assert len(verification['device']) == 4
    assert all(x['healthy'] and x['offline_float_equal'] and x['queue_empty'] == 0 and
               x['budget_exceeded'] == 0 for x in verification['device'].values())
    take = verification['take']
    assert take['verified'] and take['frames'] == 144123 and take['record_hash'] == take['play_hash']
    assert verification['exports'][0]['source_hash'] == verification['exports'][1]['source_hash']
    assert verification['take_schema'] == 5 and verification['control_fields'] == 27
    assert verification['old_schema4_player_preserved']
    page = a.workspace / 'research/接火低频统一驾驶V1.html'
    assert sha(page) == review['page_sha256']
    paths = set(now) | set(build['source_sha256']) | set(docs) | {
        'handoff/tools/index_sources.py', 'Launch-Catch-Study.cmd'}
    paths |= {x.relative_to(repo).as_posix() for x in (repo / 'tools').glob('*catch_drive_v1.py')}
    for folder in ('catch_bloom_v1', 'startup_settle_v1', 'startup_drive_v1'):
        paths |= {x.relative_to(repo).as_posix() for x in (repo / 'voices' / folder).iterdir() if x.is_file()}
    paths |= set(accepted)
    paths.discard(summary.relative_to(repo).as_posix())
    r = dict(
        schema='vsl.catch-drive-summary/1', date='2026-11-12',
        result='optional_unified_catch_native_and_take_integration',
        prior_commit=before['source_commit'], C_H_count=468,
        prior_C_H_count=466, prior_C_H_ownership_unchanged=True,
        prior_C_H_bytes_unchanged=466 - len(changed), modified_C_H=sorted(changed),
        new_C_H=sorted(set(now) - set(old)), catch_kernel_unchanged=True,
        system_CTests_passed=45, failed_build_preserved='build1: tests passed; summary text assertion failed',
        legacy_WAVs_byte_equal=108, legacy_control_CSVs_byte_equal=True,
        integrated_cases=verification['scene'], device=verification['device'],
        take=take, exports=verification['exports'], take_schema=5, control_fields=27,
        old_schema4_matching_player_preserved=True, native_UI_integrated=True,
        native_process_observation=native, UI_interaction_checked=False,
        human_accepted=False, accepted_exterior_pair_replaced=False,
        accepted_model_sha256=accepted, page=review['page'], clips=review['clips'],
        limits=verification['limits'] + [
            'Common fixed-filter envelope does not recover band-specific catch timing',
            'Fast catch pitch and300Hz+ DNA deficits remain',
            'Full stationary/deceleration/shift timbre and engine diversity incomplete',
            'Accepted fixed exterior DNA/LF and startup cabin candidates are distinct contexts'],
        current_source_sha256={name: sha(repo / name) for name in sorted(paths)},
        evidence_sha256=file_hashes(root))
    summary.write_text(json.dumps(r, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(result=r['result'], C_H=468, modified=len(changed), CTests=45,
                          evidence_files=len(r['evidence_sha256']), clips=len(review['clips']))))
