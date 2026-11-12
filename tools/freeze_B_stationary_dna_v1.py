"""Freeze all stationary attempts, known C fixtures and unapproved web evidence."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
summary=json.loads((repo/'research/B_stationary_dna_v1_summary.json').read_text(encoding='utf-8'))
assert summary['result']=='qualified_controls_real_sources_rejected'
assert summary['C_fixture_result']=='passed' and summary['no_new_vehicle_model']
base=a.workspace/'references/analysis/B_stationary_dna_v1'
final=base/'final1'
for item in summary['reports'].values():assert sha(a.workspace/item['path'])==item['sha256']
for name,digest in summary['sources'].items():assert sha(final/'exact_sources'/name)==digest
hashes=json.loads((final/'C_files_sha256.json').read_text(encoding='utf-8'))
assert len(hashes)==530
for name,digest in hashes.items():assert sha(repo/name)==digest
models=list(base.rglob('*.model'))
assert len(models)==2 and all('C_controls1' in path.parts for path in models)
catalog=json.loads((repo/'references/segments_v1.json').read_text(encoding='utf-8'))
assert sha(repo/'references/segments_v1.json')==sha(a.workspace/'references/segments_v1.json')
entry=catalog['sources']['B']
for key in ('raw','master','video'):assert sha(a.workspace/entry[key])==entry[key+'_sha256']
out=a.workspace/'baselines/B_stationary_dna_v1';out.mkdir(exist_ok=False)
shutil.copytree(base,out/'stationary_evidence')
shutil.copytree(a.workspace/'references/analysis/idle_source_candidates_v2',out/'metadata_only_candidates')
shutil.copytree(a.workspace/'references/analysis/cabin_low_v1/target_observe1',out/'original_unchanged_observations')
parents={}
for name in ('cabin_low_context_v1','stereo_drive_v1'):
    manifest=a.workspace/'baselines'/name/'manifest.json'
    assert manifest.exists()
    parents[name]=dict(path=str(manifest),sha256=sha(manifest))
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),commit],cwd=repo,check=True)
with zipfile.ZipFile(out/'source.zip') as archive:assert archive.testzip() is None
(out/'README.txt').write_text(
    'Stationary B source validation and metadata-only media proposal. Goal incomplete.\n'
    'All three real-source heldout checks rejected; NO new real-vehicle model.\n'
    'C_controls1 has ONLY two synthetic analytic fixtures; eight20s C WAVs are not engine auditions.\n'
    'Existing530C/H and voices unchanged; prior53CTests were not repeated.\n'
    'All36frames/fiveboards, original attempts/executed sources and unapproved HTML pages retained.\n'
    'B raw/master/video remain in the main data workspace and prior media/context archive; hashes verified before freezing.\n'
    'New media approval pending. Original A low audition not duplicated. Moving35 held unchanged.\n',encoding='utf-8')
files=[dict(path=file.relative_to(out).as_posix(),bytes=file.stat().st_size,sha256=sha(file))
       for file in sorted(out.rglob('*')) if file.is_file()]
manifest=dict(schema='vsl.freeze/1',source_commit=commit,files=files,parent_freezes=parents,
    external_source={key:entry[key] for key in ('raw','raw_sha256','master','master_sha256','video','video_sha256')},
    goal_complete=False,vehicle_timbre_accepted=False,real_profiles_exported=0)
(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for item in files:assert sha(out/item['path'])==item['sha256']
print(json.dumps(dict(result='frozen',commit=commit,files=len(files),bytes=sum(v['bytes'] for v in files))),flush=True)
