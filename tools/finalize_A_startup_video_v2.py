"""Bind visual observations, failed real-audio paths and unchanged C sources."""
import argparse,csv,json,shutil,subprocess,sys,zipfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--freeze',action='store_true')
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
root=a.workspace/'references/analysis/A_startup_video_v2'
summary=repo/'research/A_startup_video_v2_summary.json'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
docs=['research/A启动动作与仪表V2.md','research/A_startup_video_v2_annotations.json','research/A_startup_video_v2_summary.json',
      'research/动作转速与高频边界V1.md','handoff/研究续接.md','handoff/C文件索引.csv','AGENTS.md','README.md']
tools=['tools/observe_A_startup_v2.py','tools/analyze_A_startup_video_v2.py',
       'tools/review_A_startup_video_v2.py','tools/finalize_A_startup_video_v2.py',
       'tools/drive_evidence_v1/family.py','tools/drive_evidence_v1/sources.py']
if a.freeze:
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    r=read(summary)
    for name,digest in r['current_source_sha256'].items():assert sha(repo/name)==digest,name
    for name,digest in r['evidence_sha256'].items():assert sha(root/name)==digest,name
    freeze=a.workspace/'baselines/A_startup_video_v2';freeze.mkdir(exist_ok=False)
    shutil.copytree(root,freeze/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
    for name in docs+tools:
        target=freeze/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(freeze/'source.zip'),commit],cwd=repo,check=True)
    with zipfile.ZipFile(freeze/'source.zip') as archive:assert archive.testzip() is None
    files=[dict(path=x.relative_to(freeze).as_posix(),sha256=sha(x)) for x in sorted(freeze.rglob('*')) if x.is_file()]
    (freeze/'manifest.json').write_text(json.dumps(dict(schema='vsl.freeze/1',source_commit=commit,
        external_source=r['external_source'],files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    for row in files:assert sha(freeze/row['path'])==row['sha256']
    print(json.dumps(dict(result='frozen',files=len(files),commit=commit)));sys.exit()
o=read(root/'observation1/report.json');d=read(root/'analysis1/report.json');v=read(root/'review1/report.json')
assert o['result']=='HD_local_startup_frames_decoded' and len(o['decoded_frames'])==50
assert d['result']=='indicated_shape_observed_and_coarse_family_tested' and len(d['annotated_readings'])==20
assert not d['paired_coarse_gate']['passed'] and all(not x['rows'] for x in d['paths'])
assert v['result']=='approved_A_context_and_observation_page_published'
assert sha(o['source'])==o['source_sha256']
for name,digest in d['input_sha256'].items():assert sha(name)==digest,name
for name,digest in d['source_sha256'].items():assert sha(repo/name)==digest,name
for row in v['files']:assert sha(root/'review1'/row['file'])==row['sha256']
with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as stream:index=list(csv.DictReader(stream))
assert len(index)==478
for row in index:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
r=dict(schema='vsl.A-startup-HD-summary/1',date='2026-11-12',result='instrument_shape_observed_only',
    decoded_frames=50,indicated_RPM_readings=d['annotated_readings'],indicated_shape=d['indicated_shape'],
    controller_policy=d['old_policy'],coarse_paths=d['paths'],coarse_pair_gate=d['paired_coarse_gate'],
    known_chirp_controls=d['known_chirp_coarse_controls'],runtime_changed=False,C_H_unchanged=478,
    new_CTests_run=False,phase_qualified=False,physical_RPM_calibrated=False,independent_AV_alignment=False,
    review=v,external_source=dict(path=o['source'],sha256=o['source_sha256'],whole_download_completed=False),
    input_sha256=d['input_sha256'],limits=d['limits'],
    current_source_sha256={name:sha(repo/name) for name in docs+tools if name!='research/A_startup_video_v2_summary.json'},
    evidence_sha256={x.relative_to(root).as_posix():sha(x) for x in sorted(root.rglob('*')) if x.is_file()})
summary.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],C_H=r['C_H_unchanged'],readings=len(r['indicated_RPM_readings']))))
