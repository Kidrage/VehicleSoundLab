"""Bind optional native-detail integration to exact tested sources and freeze it."""
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
    return json.loads(path.read_text(encoding='utf-8-sig'))


def hashes(root):
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts}


def index(path):
    with path.open(encoding='utf-8-sig') as stream:
        rows = list(csv.DictReader(stream))
    result = {row['文件']: row for row in rows}
    assert len(result) == len(rows)
    return result


p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', required=True, type=Path)
p.add_argument('--freeze', action='store_true')
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
root = a.workspace / 'references/analysis/startup_detail_host_v1'
summary = repo / 'research/startup_detail_host_v1_summary.json'
docs = ['README.md', 'AGENTS.md', 'handoff/算法说明.md', 'handoff/C模块与接口.md',
        'handoff/开发留痕.md', 'handoff/研究续接.md', 'handoff/C文件索引.csv',
        'research/启动细节原生接入V1.md', 'research/startup_detail_host_v1_summary.json',
        'experiments/startup_detail_host_v1/README.md', 'Launch-Startup-Detail-Study.cmd']

if a.freeze:
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
    r = read(summary)
    for name, digest in r['current_source_sha256'].items():
        assert sha(repo / name) == digest, name
    assert hashes(root) == r['evidence_sha256']
    out = a.workspace / 'baselines/startup_detail_host_v1'
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
    (out / 'manifest.json').write_text(json.dumps(dict(
        schema='vsl.startup-detail-host-freeze/1', source_commit=revision,
        human_accepted=False, native_integrated=True, programmatic_controls_checked=True,
        visual_QA=False, long_run_checked=False, physical_12speakers_checked=False,
        files=files), ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    for row in files:
        assert sha(out / row['path']) == row['sha256'], row['path']
    print(json.dumps(dict(path=str(out), files=len(files), commit=revision)))
else:
    before = read(root / 'before/report.json')
    build = read(root / 'build1/report.json')
    verification = read(root / 'verification1/report.json')
    native = read(root / 'native1/report.json')
    links = read(root / 'review_links1/report.json')
    assert before['result'] == 'schema5_sources_players_preserved'
    assert build['result'] == 'build_and_46tests_pass'
    assert verification['result'] == 'native_startup_detail_function_pass'
    for name, digest in build['source_sha256'].items():
        assert sha(repo / name) == sha(root / 'build1/exact_sources' / name) == digest, name
    for name, digest in verification['binaries'].items():
        assert sha(root / 'verification1/bin' / name) == digest, name
        assert sha(Path(build['build']) / 'bin/Release' / name) == digest, name
    assert native['responding'] and not native['has_exited']
    assert native['binary_sha256'] == verification['binaries']['VslAtlasMonitor.exe']
    assert links['result'] == 'HTTP_pages_and_audio_bytes_pass' and len(links['pages']) == 5
    assert sum(len(row['audio']) for row in links['pages']) == 32
    old = index(root / 'before/C文件索引.csv')
    now = index(repo / 'handoff/C文件索引.csv')
    assert len(old) == 469 and len(now) == 472 and set(old) <= set(now)
    changed = []
    for name, row in now.items():
        assert sha(repo / name) == row['SHA-256'], name
        if name in old:
            assert {k: v for k, v in old[name].items() if k != 'SHA-256'} == {
                k: v for k, v in row.items() if k != 'SHA-256'}, name
            if row['SHA-256'] != old[name]['SHA-256']:
                changed.append(name)
    assert len(changed) == 5 and all(n.startswith('experiments/') for n in changed)
    added = sorted(set(now) - set(old))
    assert added == ['experiments/startup_detail_host_v1/checks.c',
                     'experiments/startup_detail_host_v1/ui_checks.c',
                     'experiments/startup_detail_host_v1/ui_checks.h']
    accepted = read(repo / 'research/catch_drive_v1_summary.json')['accepted_model_sha256']
    for name, digest in accepted.items():
        assert sha(repo / name) == digest, name
    assert [verification['UI'][name]['checks'] for name in ('catch', 'startup-detail')] == [12, 14]
    assert all(row['passed'] and not row['audio_started'] for row in verification['UI'].values())
    assert len(verification['device']) == 4
    assert all(row['healthy'] and row['offline_float_equal'] and row['queue_empty'] == 0
               and row['budget_exceeded'] == 0 for row in verification['device'].values())
    take = verification['take']
    assert take['verified'] and take['frames'] == 144123 and take['record_hash'] == take['play_hash']
    assert verification['exports'][0]['source_hash'] == verification['exports'][1]['source_hash']
    assert verification['renderer_identity_unchanged'] and verification['old_schema5_output_and_source_hash_equal']
    paths = set(now) | set(build['source_sha256']) | set(accepted) | set(docs)
    paths |= {'handoff/tools/index_sources.py'}
    paths |= {x.relative_to(repo).as_posix() for x in (repo / 'tools').glob('*startup_detail_host_v1.py')}
    for folder in ('startup_settle_v1', 'startup_detail_v1', 'startup_drive_v1', 'catch_bloom_v1'):
        paths |= {x.relative_to(repo).as_posix() for x in (repo / 'voices' / folder).iterdir() if x.is_file()}
    paths.discard(summary.relative_to(repo).as_posix())
    r = dict(schema='vsl.startup-detail-host-summary/1', date='2026-11-12',
             result='optional_native_detail_function_verified', prior_commit=before['commit'],
             C_H_count=472, prior_C_H_count=469, prior_C_H_ownership_unchanged=True,
             prior_C_H_bytes_unchanged=464, modified_C_H=changed, new_C_H=added,
             runtime_libraries_unchanged=True, system_CTests_passed=46,
             native_integrated=True, UI_programmatic=verification['UI'],
             device=verification['device'], take=take, exports=verification['exports'],
             old_schema5_take=verification['old_schema5_take'], renderer_identity_unchanged=True,
             take_schema=5, control_fields=27, native_observation=native,
             state_review_links=links,
             human_accepted=False, visual_QA=False, accepted_model_sha256=accepted,
             limits=verification['limits'] + [
                 'Full startup pitch/timing and other-state timbre comparisons incomplete',
                 'Approved source references and functional state demos are not matched timbre acceptance'],
             current_source_sha256={name: sha(repo / name) for name in sorted(paths)},
             evidence_sha256=hashes(root))
    summary.write_text(json.dumps(r, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(result=r['result'], C_H=472, CTests=46, UI=[12, 14],
                          evidence_files=len(r['evidence_sha256']))))
