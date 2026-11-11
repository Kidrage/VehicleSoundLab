"""Freeze all deceleration observations, including failed carriers and preparation."""
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
summary = json.loads((repo/'research/cabin_decel_v1_summary.json').read_text(encoding='utf-8'))
assert not summary['runtime_changes'] and summary['phase_candidate_qualification'] == 'not_passed'
assert summary['raw_band_validation'] == 'pass'
root = args.workspace/'references/analysis/cabin_decel_v1'
assert str(root) == summary['evidence_root']
for name, digest in summary['source_sha256'].items():
    assert sha(repo/name) == digest, name
for name, digest in summary['evidence_sha256'].items():
    assert sha(root/name) == digest, name
for name, digest in summary['input_metadata_sha256'].items():
    assert sha(args.workspace/name) == digest, name
old = args.workspace/'baselines/shift_repeat_v1'
assert sha(old/'manifest.json') == summary['prior_visual_evidence_manifest_sha256']
old_manifest = json.loads((old/'manifest.json').read_text(encoding='utf-8'))
out = args.workspace/'baselines/cabin_decel_v1'
out.mkdir(exist_ok=False)
shutil.copytree(root, out/'evidence', ignore=shutil.ignore_patterns('__pycache__'))
for name in summary['input_metadata_sha256']:
    target = out/'input_metadata'/name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.workspace/name, target)
for row in old_manifest['files']:
    name = row['path']
    if name.startswith('evidence/exploration1/frame_') or name.startswith('evidence/exploration1/sheet_') or name in (
            'evidence/exploration1/report.json', 'docs/shift_repeat_v1_annotations.json'):
        assert sha(old/name) == row['sha256']
        target = out/'prior_visual'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old/name, target)
shutil.copy2(old/'manifest.json', out/'prior_visual/manifest.json')
(out/'docs').mkdir()
for name in ('research/车内减速声纹V1.md', 'research/cabin_decel_v1_summary.json',
             'research/cabin_decel_v1_plan.json', 'research/cabin_decel_v1_higher_carriers.json',
             'research/cabin_decel_v1_clock.png', 'handoff/研究续接.md'):
    shutil.copy2(repo/name, out/'docs'/Path(name).name)
revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
subprocess.run(['git', 'archive', '--format=zip', '--output='+str(out/'source.zip'), revision], cwd=repo, check=True)
with zipfile.ZipFile(out/'source.zip') as archive:
    assert archive.testzip() is None
(out/'README.txt').write_text('车内减速声纹V1，提交：'+revision+'\n'
    '相位候选未通过；原始宽频带功率算式与已知变化控制通过。没有新DNA／状态映射或音色认可。\n'
    '保留两种相位窗、较高谱线的失败、相对计划路径失败、实际执行源码与原PTS画面。\n'
    '原始视频／float主文件按既有交接Release与provenance SHA恢复。\n'
    '不要把混合录音总功率补进谐波；不要把L/R观察直接当成两个引擎声源。\n', encoding='utf-8')
files = [dict(path=p.relative_to(out).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
         for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.cabin-deceleration-freeze/1',
    source_commit=revision, runtime_changes=False, human_accepted=False, files=files),
    ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
for row in files:
    assert sha(out/row['path']) == row['sha256']
print(json.dumps(dict(path=str(out), commit=revision, files=len(files),
                     bytes=sum(r['bytes'] for r in files)), ensure_ascii=False))
