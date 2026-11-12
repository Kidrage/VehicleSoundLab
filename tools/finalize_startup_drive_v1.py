"""Bind the integrated startup proof to its sources, or freeze the committed stage."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def doc(path):
    return json.loads(path.read_text(encoding='utf-8'))

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--freeze', action='store_true')
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
root = a.workspace / 'references/analysis/startup_drive_v1'
summary = repo / 'research/startup_drive_v1_summary.json'
docs = ['research/启动层统一驾驶V1.md', 'research/startup_drive_v1_summary.json',
        'handoff/算法说明.md', 'handoff/C模块与接口.md', 'handoff/研究续接.md',
        'handoff/开发留痕.md', 'handoff/C文件索引.csv', 'AGENTS.md', 'Launch-Startup-Study.cmd']

if a.freeze:
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
    r = doc(summary)
    for name, digest in r['current_source_sha256'].items():
        assert sha(repo/name) == digest, name
    for name, digest in r['evidence_sha256'].items():
        assert sha(root/name) == digest, name
    assert sha(repo/'handoff/C文件索引.csv') == r['c_index_sha256']
    out = a.workspace / 'baselines/startup_drive_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(root, out/'evidence', ignore=shutil.ignore_patterns('__pycache__'))
    (out/'docs').mkdir()
    for name in docs:
        shutil.copy2(repo/name, out/'docs'/Path(name).name)
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    subprocess.run(['git', 'archive', '--format=zip', '--output='+str(out/'source.zip'), revision], cwd=repo, check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    files = [dict(path=x.relative_to(out).as_posix(), bytes=x.stat().st_size, sha256=sha(x))
             for x in sorted(out.rglob('*')) if x.is_file()]
    (out/'manifest.json').write_text(json.dumps(dict(schema='vsl.startup-drive-freeze/1',
        source_commit=revision, human_accepted=False, full_startup_complete=False,
        hardware12_checked=False, files=files), ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    for row in files:
        assert sha(out/row['path']) == row['sha256']
    print(json.dumps(dict(path=str(out), commit=revision, files=len(files), bytes=sum(x['bytes'] for x in files))))
else:
    before = doc(root/'before/report.json')
    build = doc(root/'build2/report.json')
    verified = doc(root/'verification1/report.json')
    review = doc(root/'review1/report.json')
    assert build['result'] == 'build_and_43tests_pass'
    assert verified['result'] == 'integrated_startup_function_pass'
    assert review['result'] == 'listening_page_published'
    for name, digest in build['source_sha256'].items():
        assert sha(repo/name) == digest, name
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as stream:
        rows = list(csv.DictReader(stream))
    now = {row['文件']: row['SHA-256'] for row in rows}
    assert len(now) == len(rows) == 455
    for name, digest in now.items():
        assert sha(repo/name) == digest, name
    old = before['C_H_sha256']
    assert len(old) == 454 and set(old) <= set(now)
    with (root/'before/C文件索引.csv').open(encoding='utf-8-sig') as stream:
        old_rows = {row['文件']: row for row in csv.DictReader(stream)}
    for row in rows:
        name = row['文件']
        if name in old_rows and not name.startswith('modules/start_texture/'):
            for field in ('模块', '构建归属', '职责'):
                assert row[field] == old_rows[name][field], (name, field)
    accepted = {
        'voices/dna_bank_v1/V10 Exterior.model': '6f8992e6674f603334f82bdbc526fd8ac5bbe750606154c5e83c166c077bb1b7',
        'voices/coherent_low_v1/measured_phase.model': '9e456a4198bce540a4ccc60220b9cf86e40dc80eadc8d1c2904dc5248715e895'}
    for name, digest in accepted.items():
        assert sha(repo/name) == digest
    window = doc(root/'native_window.json')
    assert any(x['Responding'] and x['MainWindowTitle'].endswith('Startup Study') for x in window)
    sources = dict(build['source_sha256'])
    extras = [*docs, 'README.md', 'modules/start_texture/README.md', 'handoff/tools/index_sources.py']
    extras += [x.relative_to(repo).as_posix() for x in (repo/'tools').glob('*startup_drive_v1.py')]
    extras += [x.relative_to(repo).as_posix() for x in (repo/'voices/startup_drive_v1').glob('*') if x.is_file()]
    for name in extras:
        if name != summary.relative_to(repo).as_posix():
            sources[name] = sha(repo/name)
    evidence = {x.relative_to(root).as_posix(): sha(x) for x in sorted(root.rglob('*'))
                if x.is_file() and '__pycache__' not in x.parts}
    r = dict(schema='vsl.startup-drive-summary/1', date='2026-11-12', result='optional_integration_function_pass',
        before_commit=before['commit'], C_H_count=len(now), new_C_H=sorted(set(now)-set(old)),
        changed_C_H=sorted(x for x in old if old[x] != now[x]),
        unchanged_C_H=sum(now[x] == old[x] for x in old), prior_ownership_preserved_except_start_texture=True,
        accepted_model_sha256=accepted, CTests=43, take_schema=4, control_fields=26,
        legacy=verified['legacy'], startup=verified['startup'], device=verified['device'],
        take=verified['take'], exports=verified['exports'], page=review['page'],
        human_accepted=False, UI_interaction_checked=False, hardware12_checked=False,
        limitations=verified['limits'] + ['Catching combustion and LF buildup absent',
            'A 240-frame/5ms offline overruns remain; no long-run/hard realtime guarantee'],
        current_source_sha256=sources, c_index_sha256=sha(repo/'handoff/C文件索引.csv'), evidence_sha256=evidence)
    summary.write_text(json.dumps(r, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({k:r[k] for k in ['result','C_H_count','new_C_H','unchanged_C_H','CTests','take_schema']}))
