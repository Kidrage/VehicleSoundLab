"""Archive startup/controller evidence, exact working sources and both binaries."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from startup_response_evidence_v1 import sha,verify


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    evidence=data/'renders/startup_response_v1';review=data/'references/analysis/startup_response_v1/review1'
    native=read(evidence/'verification2/report.json');ui=read(evidence/'ui2/report.json');web=read(evidence/'web1/report.json')
    assert native['result']==ui['result']==web['result']=='passed'
    assert len(native['original_v3_exact'])==12 and native['custom_peak_rpm']==2000
    assert native['final_state']['lifecycle']==0 and ui['final_state']['underflows']==0
    for name,report in (('verification2',native),('ui2',ui)):
        path=evidence/name/'source_binding.json';assert sha(path)==report['source_binding_sha256']
        binding=read(path);verify(repo,binding)
        for row in binding['files']:assert sha(evidence/name/'exact_sources'/row['path'])==row['sha256']
    new=repo/'build-vehicle-source-v4/bin/Release/vsl_source_bridge.dll'
    old=repo/'build-vehicle-source-v3/bin/Release/vsl_source_bridge.dll'
    author=repo/'build-event-synth-v1/bin/Release/vsl_event_author_bridge.dll'
    assert sha(new)==native['bridge_sha256'] and sha(old)==native['old_bridge_sha256']
    assert sha(review/'app.js')==sha(repo/'tools/event_band_review_web_v1.js')
    assert sha(review/'executed_build.py')==sha(repo/'tools/build_startup_response_review_v1.py')
    reviewed=read(review/'report.json');assert reviewed['bridge_sha256']==sha(new)
    for name,digest in reviewed['files'].items():assert sha(review/name)==digest,name
    previous=data/'baselines/event_band_scope_v1/delivery1';voices=[]
    for source in sorted((repo/'voices').rglob('*')):
        if source.is_file():
            name=source.relative_to(repo);assert sha(source)==sha(previous/'repo'/name),str(name)
            voices.append(name.as_posix())
    assert len(voices)==89
    report=dict(schema='vsl.startup-response-milestone/1',created=datetime.now(timezone.utc).isoformat(),
        previous_goal_turn='no progress: source/render boundary and compute scope confirmation only',
        this_goal_turn='progress: per-engine startup C configuration, independent editor, identity-bound recipes/replay/export, original-binary tests, full-cycle UI and original-B context evidence',
        goal_complete=False,timbre_accepted=False,new_timbre_model=False,deep_optimization=False,
        source_bridge_sha256=sha(new),legacy_bridge_sha256=sha(old),author_bridge_sha256=sha(author),
        unchanged_voice_files=voices,native=native,ui=ui,web=web,
        review_url='http://127.0.0.1:8789/references/analysis/startup_response_v1/review1/index.html',
        source_context=str(data/'references/analysis/event_sources_v1/timelines3/B_catch'),
        limitations=[
            '2000 RPM is an engineering comparison against rough indicated 1800..2500, not measured engine/AV/order calibration.',
            'No new startup timbre accepted; only old A mixed-cabin crank/catch profiles in formal bank.',
            'Afterfire, shift, engage, disengage and stop material profiles still missing; local scoped tailpipe candidate is unclassified.',
            'B onset LF ownership and precise startup state uncertain; no B profile fitted or promoted.',
            'G1/G2/G3 source approval and previous listening questions pending; no new downloads.',
            'Bounded muted32s device check is not a soak or ADI timing qualification; no spatial scope or compute optimization.',
            'Persistent updated launch/restart remains unexecuted after previous automatic rejection blocked by policy; no bypass.',
            'No commit or push this milestone; original V3 takes remain version-bound to their freeze.'
        ])
    (repo/'research/startup_response_v1_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    subprocess.run(['git','diff','--check'],cwd=repo,check=True)
    a.output.mkdir(parents=True,exist_ok=False)
    subprocess.run(['git','diff','--binary','--output='+str(a.output/'working-tree.patch')],cwd=repo,check=True)
    names=set()
    for args in [('diff','--name-only','-z'),('ls-files','--others','--exclude-standard','-z')]:
        names.update(v for v in subprocess.check_output(['git',*args],cwd=repo).decode('utf-8').split('\0') if v)
    names.update(row['path'] for row in read(evidence/'verification2/source_binding.json')['files'])
    for name in sorted(names):
        source=repo/name
        if source.is_file():
            target=a.output/'repo'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    shutil.copytree(evidence,a.output/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(review,a.output/'review')
    shutil.copytree(data/'references/analysis/event_sources_v1/timelines3/B_catch',a.output/'B_source_context')
    rejection=data/'renders/event_system_v1/launch1/approval-rejections.json'
    shutil.copy2(rejection,a.output/'prior-launch-rejections.json')
    for label,binary in (('source-v4',new),('source-v3-preserved',old),('event-author-preserved',author)):
        target=a.output/'binaries'/label/binary.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(binary,target)
    manifest=dict(schema='vsl.startup-response-delivery/1',created=datetime.now(timezone.utc).isoformat(),
        base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        goal_complete=False,timbre_accepted=False,bridge_sha256=sha(new),old_bridge_sha256=sha(old),
        files=[dict(path=p.relative_to(a.output).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
               for p in sorted(a.output.rglob('*')) if p.is_file()])
    (a.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    for row in manifest['files']:
        target=a.output/row['path'];assert target.stat().st_size==row['bytes'] and sha(target)==row['sha256']
    print(json.dumps(dict(output=str(a.output),files=len(manifest['files']),bytes=sum(r['bytes'] for r in manifest['files']),
        goal_complete=False,unchanged_voices=len(voices)),ensure_ascii=False))


if __name__=='__main__':main()
