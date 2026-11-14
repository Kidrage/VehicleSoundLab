"""Protect current C/models and the strict old take player before source edits."""
import argparse,csv,shutil,subprocess
from pathlib import Path
from research_archive_v1 import load,save,sha
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];out=a.workspace/'references/analysis/layer_monitor_v1/before';out.mkdir(parents=True,exist_ok=False)
rows=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
assert len(rows)==620 and all(sha(repo/row[0])==row[4] for row in rows[1:])
voices=load(a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json')
assert len(voices)==67 and all(sha(repo/name)==digest for name,digest in voices.items())
files={}
for name in [row[0] for row in rows[1:]]+['handoff/C文件索引.csv','research/layer_monitor_v1_plan.json',
    'tools/prepare_layer_monitor_v1.py','modules/atlas_take/CMakeLists.txt','handoff/CMakeLists.txt']:
    dest=out/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);files[name]=sha(repo/name)
for name in ['VslAtlasTake_render.exe','VslAtlasMonitor.exe']:
    path=repo/'build-fine-idle-drive-v1/bin/Release'/name
    dest=out/'bin'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest);files['old-bin/'+name]=sha(path)
save(out/'voice_hashes.json',voices)
save(out/'report.json',dict(result='protected_before_edits',commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    files=files,C_H=619,voices=67,old_schema10_player_preserved=True))
print(dict(result='protected_before_edits',C_H=619,voices=67,files=len(files)))
