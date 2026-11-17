"""Bind current authoring/material evidence; preserve unsuccessful attempts."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024**2),b''):h.update(b)
    return h.hexdigest()


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    evidence=data/'renders/event_band_scope_v1';review=data/'references/analysis/event_band_scope_v1'
    previous=data/'baselines/vehicle_lifecycle_v1/delivery1'
    verified=read(evidence/'verification3/verification.json');regression=read(evidence/'regression2/verification.json')
    material=read(evidence/'material1/report.json');web=read(evidence/'review-web4/report.json')
    assert all(r['result']=='passed' for r in (verified,regression,material,web))
    assert verified['ui']['result']=='passed' and regression['ui']['result']=='passed'
    assert verified['unqualified_fit_preserves_model'] and material['all_four_tested_seeds_within_3db']
    assert sha(review/'review3/analysis/profile.json')==material['source_profile_sha256']
    assert sha(review/'review3/executed_build.py')==sha(repo/'tools/build_event_band_review_v1.py')
    assert sha(review/'review3/app.js')==sha(repo/'tools/event_band_review_web_v1.js')
    # The final scope/backend tests captured their exact Python/UI verifier.
    assert sha(evidence/'verification3/executed_verification.py')==sha(repo/'tools/verify_event_band_scope_v1.py')
    for name in ('author_event.py',*['event_authoring/'+p.name for p in (repo/'tools/event_authoring').glob('*.py')],
                 *['event_designer/'+p.name for p in (repo/'tools/event_designer').glob('*.py')]):
        assert sha(repo/'tools'/name)==sha(review/'review3/exact_sources'/name),name
    unchanged=[]
    for folder in ('voices','modules/event_synth','modules/event_control','modules/vehicle_source'):
        for path in sorted((repo/folder).rglob('*')):
            if path.is_file():
                name=path.relative_to(repo);assert sha(path)==sha(previous/'repo'/name),str(name)
                unchanged.append(name.as_posix())
    source_dll=repo/'build-vehicle-source-v3/bin/Release/vsl_source_bridge.dll'
    author_dll=repo/'build-event-synth-v1/bin/Release/vsl_event_author_bridge.dll'
    previous_manifest=read(previous/'manifest.json')
    assert sha(source_dll)==previous_manifest['bridge_sha256']
    assert sha(author_dll)==verified['renderer_sha256']==material['renderer_sha256']
    report=dict(schema='vsl.event-band-scope-milestone/1',created=datetime.now(timezone.utc).isoformat(),
        previous_goal_turn='no progress toward implementation: source/render boundary and budget confirmation only',
        this_goal_turn='progress: scoped authoring/UI/provenance, finite-response band calibration/refusal, real tailpipe candidate, C/import/history/browser evidence and review seek fix',
        goal_complete=False,timbre_accepted=False,verification=verified,regression=regression,material=material,web=web,
        source_bridge_sha256=sha(source_dll),event_author_sha256=sha(author_dll),unchanged_files=unchanged,
        global_event_bank_unchanged=True,new_downloads=False,new_C_or_runtime_DSP=False,deep_optimization=False,
        review_url='http://127.0.0.1:8789/references/analysis/event_band_scope_v1/review3/index.html',
        editable_project=read(review/'review3/report.json')['editable_project'],
        limitations=['Only a scoped tailpipe acoustic increment, not confirmed afterfire or complete full-band event.',
            'Original reference retains continuous/background sound. No waveform physical-source separation.',
            'Band fit and four tested seeds do not establish transient fidelity, naturalness or all random seeds.',
            'Original crank/catch remain unaccepted; automatic afterfire/other mechanical bank types still unavailable.',
            'Startup hearing and G1/G2/G3 source approvals remain pending; no acceptance inferred.',
            'Persistent launch/restart was previously automatically rejected: blocked by policy. No bypass or new persistent launch.',
            'No ADI timing, spatial feature, new commit or push.'])
    (repo/'research/event_band_scope_v1_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    a.output.mkdir(parents=True,exist_ok=False)
    subprocess.run(['git','diff','--check'],cwd=repo,check=True)
    subprocess.run(['git','diff','--binary','--output='+str(a.output/'working-tree.patch')],cwd=repo,check=True)
    names=set()
    for args in [('diff','--name-only','-z'),('ls-files','--others','--exclude-standard','-z')]:
        names.update(v for v in subprocess.check_output(['git',*args],cwd=repo).decode('utf-8').split('\0') if v)
    for folder in ('tools/event_authoring','tools/event_designer','tools/sound_designer','modules/event_synth','modules/event_control',
                   'modules/vehicle_source','voices'):
        names.update(p.relative_to(repo).as_posix() for p in (repo/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    for name in sorted(names):
        source=repo/name
        if source.is_file():
            target=a.output/'repo'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    shutil.copytree(evidence,a.output/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(review,a.output/'reviews')
    shutil.copytree(data/'references/analysis/event_sources_v1/timelines2',a.output/'source_timeline')
    shutil.copy2(source_dll,a.output/source_dll.name);shutil.copy2(author_dll,a.output/author_dll.name)
    manifest=dict(schema='vsl.event-band-scope-delivery/1',created=datetime.now(timezone.utc).isoformat(),
        base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        goal_complete=False,timbre_accepted=False,source_bridge_sha256=sha(source_dll),event_author_sha256=sha(author_dll),
        files=[dict(path=p.relative_to(a.output).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
               for p in sorted(a.output.rglob('*')) if p.is_file()])
    (a.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    for row in manifest['files']:assert sha(a.output/row['path'])==row['sha256']
    print(json.dumps(dict(output=str(a.output),files=len(manifest['files']),bytes=sum(r['bytes'] for r in manifest['files']),
        goal_complete=False,unchanged_files=len(unchanged)),ensure_ascii=False))


if __name__=='__main__':main()
