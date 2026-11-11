"""Freeze the runnable auxiliary-layer system, evidence and committed sources."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
summary = repo / 'research/drive_aux_v1_summary.json'
record = json.loads(summary.read_text(encoding='utf-8'))
assert record['result'] == 'pass' and record['tests'] == 37 and not record['human_accepted']
root = Path(record['evidence_root'])
for name, digest in record['source_sha256'].items():
    assert sha(repo / name) == digest, name
for name, digest in record['evidence_sha256'].items():
    assert sha(root / name) == digest, name
for name, digest in record['binary_sha256'].items():
    assert sha(repo / 'handoff-build/bin/Release' / name) == digest, name
assert sha(repo / 'handoff/C文件索引.csv') == record['c_index_sha256']
revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
out = args.workspace / 'baselines/drive_aux_v1'
out.mkdir(exist_ok=False)
shutil.copytree(root, out / 'evidence', ignore=shutil.ignore_patterns('__pycache__'))
for folder in ('exterior_anchors_v1', 'cabin_anchors_v1', 'residual_atlas_v1'):
    shutil.copytree(repo / 'voices' / folder, out / 'voices' / folder)
(out / 'bin').mkdir()
for name in record['binary_sha256']:
    shutil.copy2(repo / 'handoff-build/bin/Release' / name, out / 'bin' / name)
(out / 'docs').mkdir()
for path in (summary, repo / 'research/驾驶辅助声层V1.md', repo / 'modules/drive_aux/README.md',
             repo / 'handoff/C模块与接口.md', repo / 'handoff/C文件索引.csv', repo / 'handoff/算法说明.md'):
    shutil.copy2(path, out / 'docs' / path.name)
subprocess.run(['git', 'archive', '--format=zip', '--output=' + str(out / 'source.zip'), revision], cwd=repo, check=True)
with zipfile.ZipFile(out / 'source.zip') as archive:
    assert archive.testzip() is None
(out / 'Run-DNA-Drive.cmd').write_bytes(b'@echo off\r\ncd /d "%~dp0"\r\nstart "" "bin\\VslAtlasMonitor.exe"\r\n')
(out / 'README.txt').write_text('驾驶辅助声层V1\n提交：' + revision + '\n'
    'Run-DNA-Drive.cmd打开统一驾驶UI；默认停止／未点火／新增五层0%。\n'
    '声层下拉框选择进气／机械／空气／道路／风，共用滑条分别记值。\n'
    'evidence/review/index.html有同增益对照与独奏；新增音色尚未听评。\n'
    '当前行程.vslrun schema2/25字段，旧schema1必须用旧冻结播放器。\n'
    '37项C契约、A/E各19旧音轨一致、2/12源一致、短时静音设备录制回放通过。\n'
    '没有完成实录声源分离／全工况谱形／长期硬实时／UI目视或实际7.1.4验收。\n'
    '批准原素材与旧Release另存；本包是增量研究快照。\n', encoding='utf-8')
files = [dict(path=p.relative_to(out).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
         for p in sorted(out.rglob('*')) if p.is_file()]
(out / 'manifest.json').write_text(json.dumps(dict(schema='vsl.driving-auxiliary-freeze/1', source_commit=revision,
    human_accepted=False, summary_sha256=sha(summary), files=files), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
for item in files:
    assert sha(out / item['path']) == item['sha256']
print(json.dumps(dict(path=str(out), commit=revision, files=len(files), bytes=sum(r['bytes'] for r in files)), ensure_ascii=False))
