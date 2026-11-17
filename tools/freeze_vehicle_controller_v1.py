"""Freeze the reviewable controller milestone without changing Git or sound."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--checks',type=Path,required=True);args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1];base=Path('E:/VehicleSoundLab/renders/vehicle_controller_v1')
    ui=load(base/'verification6/verification.json');current=load(args.checks/'verification.json');launch=load(base/'launch1/verification.json')
    assert ui['ui'] and ui['restart_during_stopping'] and current['replay_pcm_exact'] and current['parameter_identity_mismatch_rejected']
    assert ui['bridge_sha256']==current['bridge_sha256'] and launch['independent_window_ready']
    regress=load(base/'legacy-regression.json');assert len(regress)==12 and all(row['exact'] for row in regress)
    args.output.mkdir(parents=True,exist_ok=False)
    subprocess.run(['git','diff','--binary','--output='+str(args.output/'working-tree.patch')],cwd=repo,check=True)
    untracked=subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'],cwd=repo).decode('utf-8').split('\0')
    selected=set(name for name in untracked if name)
    selected.update(['CMakeLists.txt','AGENTS.md','modules/atlas_drive/render.c','src/drive/drive.c','src/drive/drive.h',
        'src/drive/kinematic.c','src/drive/kinematic.h','tools/sound_designer/server.py','tools/sound_designer/web/app.js'])
    for folder in ('modules/vehicle_source','modules/vehicle_input','experiments/vehicle_source_v1','tools/vehicle_controller','voices'):
        selected.update(path.relative_to(repo).as_posix() for path in (repo/folder).rglob('*')
                        if path.is_file() and '__pycache__' not in path.parts)
    for name in sorted(selected):
        source=repo/name;target=args.output/'repo'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    binary=repo/'build-vehicle-source-v1/bin/Release/vsl_source_bridge.dll';assert digest(binary)==current['bridge_sha256']
    shutil.copy2(binary,args.output/binary.name)
    for label,path in [('ui',base/'verification6/verification.json'),('replay',args.checks/'verification.json'),
        ('launch',base/'launch1/verification.json'),('legacy',base/'legacy-regression.json'),('ctest',base/'source-check-final.log')]:
        shutil.copy2(path,args.output/(label+path.suffix))
    for name in ('drive','tone','signals'):shutil.copy2(base/'verification6'/(name+'.png'),args.output/(name+'.png'))
    manifest=dict(schema='vsl.vehicle-controller-milestone/1',base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        goal_complete=False,source_only=True,bridge_sha256=current['bridge_sha256'],voices_sha256=current['voices_sha256'],
        files=[dict(path=path.relative_to(args.output).as_posix(),sha256=digest(path),bytes=path.stat().st_size)
               for path in sorted(args.output.rglob('*')) if path.is_file()])
    (args.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(archive=str(args.output),files=len(manifest['files']),goal_complete=False),indent=2))

if __name__=='__main__':main()
