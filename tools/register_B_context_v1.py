"""Register the verified approved context video; preserve both previous catalogs."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--fetch',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
a.out.mkdir(parents=True,exist_ok=False)
shutil.copy2(__file__,a.out/'executed_register.py')
report = json.loads((a.fetch/'report.json').read_text(encoding='utf-8'))
assert report['result']=='downloaded_video_context_not_aligned'
assert report['url']=='https://www.youtube.com/watch?v=qmp1SVhmXgU'
assert sha(Path(report['file']))==report['sha256']
assert sha(a.fetch/'executed_fetch.py')==report['source_sha256']
relative = 'references/raw/B_context_720p.mp4'
target = a.workspace/relative
assert not target.exists()
catalogs = [repo/'references/segments_v1.json',a.workspace/'references/segments_v1.json']
before = []
for i,path in enumerate(catalogs):
    data=json.loads(path.read_text(encoding='utf-8'))
    assert data['sources']['B']['video'] is None
    assert data['sources']['B']['url']==report['url']
    backup=a.out/f'catalog_before_{i}.json';shutil.copy2(path,backup)
    before.append(dict(path=str(path),sha256=sha(path),backup_sha256=sha(backup)))
shutil.copy2(report['file'],target)
assert sha(target)==report['sha256']
after=[]
for path in catalogs:
    data=json.loads(path.read_text(encoding='utf-8'))
    data['sources']['B'].update(video=relative,video_sha256=report['sha256'],
        alignment='Approved 720p context video retrieved2026-11-12; user MP3 to video/audio alignment not yet measured. Do not directly transfer frame timestamps to existing audio.')
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    after.append(dict(path=str(path),sha256=sha(path)))
r=dict(schema='vsl.b-context-registration/1',result='registered_not_aligned',
    fetch_report_sha256=sha(a.fetch/'report.json'),source_sha256=sha(Path(__file__)),
    video=relative,video_sha256=sha(target),catalogs_before=before,catalogs_after=after,
    audio_master_modified=False)
(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(r,ensure_ascii=False),flush=True)
