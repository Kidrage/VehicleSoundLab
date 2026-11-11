"""Freeze the optional AM experiment, including the failed executable path."""
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
summary = json.loads((repo/'research/residual_motion_v1_summary.json').read_text(encoding='utf-8'))
assert summary['technical_validation'] == 'pass' and summary['real_context_timbre_improvement'] == 'not_established'
assert not summary['human_accepted'] and not summary['driving_attached']
root = args.workspace/'references/analysis/residual_motion_v1'
assert str(root) == summary['evidence_root']
for name, digest in summary['source_sha256'].items():
    assert sha(repo/name) == digest, name
for name, digest in summary['evidence_sha256'].items():
    assert sha(root/name) == digest, name
assert sha(summary['review']['page']) == summary['review']['page_sha256']
out = args.workspace/'baselines/residual_motion_v1'
out.mkdir(exist_ok=False)
shutil.copytree(root, out/'evidence', ignore=shutil.ignore_patterns('__pycache__'))
shutil.copy2(summary['review']['page'], out/'review_original.html')
# The original page's relative links target the live workspace. Provide a
# separate portable page, preserving the original bytes and hash as evidence.
html = Path(summary['review']['page']).read_text(encoding='utf-8')
html = html.replace('../references/analysis/residual_motion_v1/review1/', 'evidence/review1/')
(out/'review.html').write_text(html, encoding='utf-8')
(out/'docs').mkdir()
for name in ('research/残差幅度细节V1.md', 'research/residual_motion_v1_summary.json',
             'handoff/C模块与接口.md', 'handoff/研究续接.md', 'handoff/C文件索引.csv'):
    shutil.copy2(repo/name, out/'docs'/Path(name).name)
revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
subprocess.run(['git', 'archive', '--format=zip', '--output='+str(out/'source.zip'), revision], cwd=repo, check=True)
with zipfile.ZipFile(out/'source.zip') as archive:
    assert archive.testzip() is None
(out/'README.txt').write_text('残差幅度细节V1，提交：'+revision+'\n'
    'C契约与已知stereo控制通过；自然度改善未建立，尚未接入驾驶／UI。\n'
    '同一短实录的三个新程序种子，误差改善约-0.007%／0.134%／0.668%，不能当成实录泛化。\n'
    'review.html为可移植同增益对照。保留verification1路径失败、实际执行源码与38项CTest日志。\n'
    '既有认可DNA／低频与旧驾驶源码保持原样；全部输入按summary及既有冻结清单SHA恢复。\n', encoding='utf-8')
files = [dict(path=p.relative_to(out).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
         for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.residual-motion-freeze/1',
    source_commit=revision, technical_validation='pass', real_context_timbre_improvement='not_established',
    human_accepted=False, files=files), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
for row in files:
    assert sha(out/row['path']) == row['sha256']
print(json.dumps(dict(path=str(out), commit=revision, files=len(files),
                     bytes=sum(r['bytes'] for r in files)), ensure_ascii=False))
