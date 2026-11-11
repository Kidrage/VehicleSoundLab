"""Freeze selected and rejected performance evidence without replacing old takes."""
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
summary = json.loads((repo/'research/atlas_perf_v1_summary.json').read_text(encoding='utf-8'))
assert summary['selected'] == 'batch_only' and summary['technical_validation'] == 'pass'
assert not summary['hard_realtime_qualified'] and not summary['timbre_changed']
root = args.workspace/'references/analysis/atlas_perf_v1'
assert str(root) == summary['evidence_root']
for name, digest in summary['source_sha256'].items():
    assert sha(repo/name) == digest, name
for name, digest in summary['evidence_sha256'].items():
    assert sha(root/name) == digest, name
out = args.workspace/'baselines/atlas_perf_v1'
out.mkdir(exist_ok=False)
shutil.copytree(root, out/'evidence', ignore=shutil.ignore_patterns('__pycache__'))
(out/'docs').mkdir()
for name in ('research/C性能核查V1.md', 'research/atlas_perf_v1_summary.json',
             'handoff/C模块与接口.md', 'handoff/研究续接.md', 'handoff/C文件索引.csv', 'AGENTS.md'):
    shutil.copy2(repo/name, out/'docs'/Path(name).name)
revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
subprocess.run(['git', 'archive', '--format=zip', '--output='+str(out/'source.zip'), revision], cwd=repo, check=True)
with zipfile.ZipFile(out/'source.zip') as archive:
    assert archive.testzip() is None
(out/'README.txt').write_text('C性能核查V1，提交：'+revision+'\n'
    '采用batch-only：相同创新只生成一次，各锚点独立AR与完整状态不变。\n'
    '39项CTest、15组场景哈希、4组控制轨迹、固定DNA整文件字节与短时静音设备录制回放通过。\n'
    'A/E三次交替离线处理耗时中位数减少5.39%/3.08%，5ms超时仍在，非硬实时认证。\n'
    'candidate2幅度缓存因变慢撤回；numeric1的FTZ/DAZ仅供诊断，未进生产线程。\n'
    '保留所有执行阶段、失败、源码与旧播放器；严格vslrun身份不放宽。\n', encoding='utf-8')
files = [dict(path=p.relative_to(out).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
         for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.atlas-performance-freeze/1',
    source_commit=revision, selected='batch_only', technical_validation='pass',
    hard_realtime_qualified=False, files=files), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
for row in files:
    assert sha(out/row['path']) == row['sha256']
print(json.dumps(dict(path=str(out), commit=revision, files=len(files),
                     bytes=sum(r['bytes'] for r in files))))
