"""Freeze the independently completed interval analysis; preserve A fetch failure."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
evidence=a.workspace/'references/analysis/tach_mapping_v1';report=evidence/'analysis1/report.json'
r=json.loads(report.read_text(encoding='utf-8'))
assert r['result']=='E_mapping_interval_sensitivity_observed'
for name,digest in r['input_sha256'].items():assert sha(name)==digest,name
for name,digest in r['source_sha256'].items():assert sha(repo/name)==digest,name
fetch=a.workspace/'references/analysis/A_hires_v1/fetch1'
failed=json.loads((fetch/'report.json').read_text(encoding='utf-8'));assert failed['result']=='failed'
summary=dict(schema='vsl.tach-mapping-summary/1',date='2026-11-12',result=r['result'],
    known_controls=r['known_controls'],sensitivities=[{k:v for k,v in x.items() if k!='rows'} for x in r['sensitivities']],
    limits=r['limits'],A_hires_fetch=failed,A_native_frame_sha256=sha(fetch/'start_36_8.png'),
    partial_video=dict(path=str(fetch/'A_picture.mp4.part'),sha256=sha(fetch/'A_picture.mp4.part'),
        bytes=(fetch/'A_picture.mp4.part').stat().st_size,whole_download_completed=False),
    source_sha256={name:sha(repo/name) for name in ('tools/analyze_tach_mapping_v1.py','tools/tach_mapping_v1/intervals.py',
        'tools/fetch_A_hires_v1.py','tools/finalize_tach_mapping_v1.py','research/转速映射证据补记V1.md')},
    runtime_mapping_or_timbre_changed=False,A_startup_RPM_calibrated=False)
path=repo/'research/tach_mapping_v1_summary.json'
path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
freeze=a.workspace/'baselines/tach_mapping_v1';freeze.mkdir(exist_ok=False)
shutil.copytree(evidence,freeze/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
for name in list(summary['source_sha256'])+['research/tach_mapping_v1_summary.json']:
    target=freeze/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)
for name in ('report.json','executed_fetch.py','start_36_8.png'):
    target=freeze/'A_fetch1'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(fetch/name,target)
files=[dict(path=x.relative_to(freeze).as_posix(),sha256=sha(x)) for x in sorted(freeze.rglob('*')) if x.is_file()]
(freeze/'manifest.json').write_text(json.dumps(dict(schema='vsl.freeze/1',external_partial_video=summary['partial_video'],files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
for row in files:assert sha(freeze/row['path'])==row['sha256']
print(json.dumps(dict(result=summary['result'],freeze_files=len(files))))
