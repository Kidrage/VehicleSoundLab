"""Freeze committed diagnostic sources, failed controls and exact C evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
summary=repo/'research/state_colour_v2_summary.json';r=json.loads(summary.read_text(encoding='utf-8'))
assert r['engineering_checks']=='pass' and r['automatic_sweep_control']=='fail' and not r['human_accepted']
root=Path(r['evidence_root'])
for p,h in r['source_sha256'].items():assert sha(repo/p)==h,p
for p,h in r['evidence_sha256'].items():assert sha(root/p)==h,p
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
out=args.workspace/'baselines/state_colour_v2';out.mkdir(exist_ok=False)
shutil.copytree(root,out/'evidence')
(out/'bin').mkdir()
for name,sub in [('VslOscColour_probe.exe','bin/Release'),('VslOscColour_checks.exe','Release')]:
    p=repo/'handoff-build'/sub/name;assert sha(p)==r['binary_sha256'][name];shutil.copy2(p,out/'bin'/name)
for folder in ('exterior_anchors_v1','state_colour_v2'):shutil.copytree(repo/'voices'/folder,out/'voices'/folder)
(out/'docs').mkdir()
for p in (summary,repo/'research/工况声线诊断V2.md',repo/'handoff/C模块与接口.md',repo/'handoff/C文件索引.csv'):
    shutil.copy2(p,out/'docs'/p.name)
(out/'inputs').mkdir();shutil.copy2(args.workspace/'references/segments_v1.json',out/'inputs/segments_v1.json')
page=(args.workspace/'research/工况声线诊断V2.html').read_text(encoding='utf-8')
(out/'review.html').write_text(page.replace('../references/analysis/state_colour_v2/','evidence/'),encoding='utf-8',newline='\n')
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),revision],cwd=repo,check=True)
(out/'README.txt').write_text('工况声线诊断V2\n提交：'+revision+'\n独立谐波幅度轴，未接入驾驶。\n'
    'C验证通过；自动扫频仍未达到0.5dB目标；音色待听评。\n'
    'evidence/review有4条持续生成试听，evidence/regression有19条新旧一致驾驶分轨。\n'
    '运行bin/VslOscColour_checks.exe检查C契约；probe参数见源码。\n'
    '旧行程仍使用atlas_take_v1冻结播放器；本轮未扩大原音色认可范围。\n',encoding='utf-8',newline='\n')
files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.state-colour-freeze/1',source_commit=revision,
    automatic_sweep_control='fail',human_accepted=False,files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
for f in files:assert sha(out/f['path'])==f['sha256']
print(json.dumps(dict(path=str(out),files=len(files),bytes=sum(f['bytes'] for f in files),commit=revision)))
