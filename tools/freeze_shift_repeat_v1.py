"""Freeze the shift comparison with exact executed sources and published code."""
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
summary = json.loads((repo / 'research/shift_repeat_v1_summary.json').read_text(encoding='utf-8'))
assert summary['result'] == 'pass' and not summary['runtime_changes']
root = args.workspace / 'references/analysis/shift_repeat_v1'
assert str(root) == summary['evidence_root']
for name, digest in summary['source_sha256'].items():
    assert sha(repo / name) == digest, name
for name, digest in summary['evidence_sha256'].items():
    assert sha(root / name) == digest, name
for name, digest in summary['input_metadata_sha256'].items():
    assert sha(args.workspace / name) == digest, name
assert sha(repo / 'research/shift_repeat_v1_comparison.png') == summary['plot_sha256']
revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
out = args.workspace / 'baselines/shift_repeat_v1'
out.mkdir(exist_ok=False)
shutil.copytree(root, out / 'evidence', ignore=shutil.ignore_patterns('__pycache__'))
(out / 'docs').mkdir()
for name in ('research/换挡跨片段复核V1.md', 'research/shift_repeat_v1_summary.json',
             'research/shift_repeat_v1_annotations.json', 'research/shift_repeat_v1_comparison.png',
             'handoff/素材下载与恢复.md'):
    shutil.copy2(repo / name, out / 'docs' / Path(name).name)
for name in summary['input_metadata_sha256']:
    target = out / 'input_metadata' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.workspace / name, target)
subprocess.run(['git', 'archive', '--format=zip', '--output=' + str(out / 'source.zip'), revision],
               cwd=repo, check=True)
with zipfile.ZipFile(out / 'source.zip') as archive:
    assert archive.testzip() is None
(out / 'README.txt').write_text(
    '换挡跨片段复核V1：离线观察，无新增运行音色。\n提交：' + revision + '\n'
    'evidence包含原PTS帧、接触表、分析、已知控制与验证；exact_sources保留实际执行的字节。\n'
    '发布版exploration只纠正一条未实现频谱去重的注释；AST一致，未改分析。\n'
    '原素材及float主文件见交接Release，按docs中的provenance/SHA恢复；此包不复制原始视频。\n'
    '实际使用的数据目录登记／批准／视频PTS索引逐字节保存在input_metadata，勿用Git副本替代。\n'
    '旧五次换挡的固定高频颜色不能推广到新片段；不辨识踏板、喷油、负载或离合时序。\n'
    '所有421项C/H字节不变，已认可DNA和相干低频不变；工程敏感度不是实录时钟误差界。\n',
    encoding='utf-8')
files = [dict(path=p.relative_to(out).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
         for p in sorted(out.rglob('*')) if p.is_file()]
manifest = dict(schema='vsl.shift-repeat-freeze/1', source_commit=revision,
                runtime_changes=False, human_accepted=False, files=files)
(out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
for row in files:
    assert sha(out / row['path']) == row['sha256']
print(json.dumps(dict(path=str(out), commit=revision, files=len(files),
                     bytes=sum(r['bytes'] for r in files)), ensure_ascii=False))
