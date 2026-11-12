"""Copy only the reviewed B context corrections into the data catalog."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
a.out.mkdir(parents=True,exist_ok=False)
shutil.copy2(__file__,a.out/'executed_register.py')
source=repo/'references/segments_v1.json';target=a.workspace/'references/segments_v1.json'
old=json.loads(target.read_text(encoding='utf-8'));new=json.loads(source.read_text(encoding='utf-8'))
assert old['sources']==new['sources']
assert old['schema']==new['schema']
changed=[key for key in new['segments'] if old['segments'][key]!=new['segments'][key]]
assert set(changed)=={'B_stationary_departure_context','B_arrival_parking_context'}
for key in old:
    if key!='segments':assert old[key]==new[key]
for key in changed:
    before=old['segments'][key];after=new['segments'][key]
    assert before['seconds']==after['seconds'] and before['allowed_uses']==after['allowed_uses']
    differences={field for field in before.keys()|after.keys() if before.get(field)!=after.get(field)}
    assert differences=={'visual','evidence','stationary_fit_status'}
shutil.copy2(target,a.out/'before_segments_v1.json')
shutil.copy2(source,target)
shutil.copy2(target,a.out/'after_segments_v1.json')
assert sha(source)==sha(target)
r=dict(schema='vsl.B-stationary-context-registration/1',result='registered',changed_segments=changed,
    before_sha256=sha(a.out/'before_segments_v1.json'),after_sha256=sha(target),
    media_or_signal_uses_or_intervals_modified=False)
(a.out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
print(json.dumps(r),flush=True)
