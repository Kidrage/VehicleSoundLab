"""Higher-resolution picture of already-approved A; no new reference identity."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
p.add_argument('--proxy',default=None)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
from yt_dlp import YoutubeDL
from yt_dlp.version import __version__

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_fetch.py')
approval_path=a.workspace/'references/approval_manifest.json'
approval=next(v for v in json.loads(approval_path.read_text(encoding='utf-8')) if v['id']=='A')
assert approval['approved'] is True and approval['video_id']=='7aZm1Wkp6QM'
r=dict(schema='vsl.A-hires-picture/1',result='running',approval_evidence=approval['approval_evidence'],
       approval_manifest_sha256=sha(approval_path),video_id=approval['video_id'],
       yt_dlp_version=__version__,browser_cookies_used=False,source_sha256=sha(__file__),
       purpose='Read existing approved startup tach; no audio re-analysis or new media identity',
       proxy='existing local HTTP proxy' if a.proxy else 'default network')
options=dict(format='bestvideo[height<=1080]',outtmpl=str(a.out/'A_picture.%(ext)s'),
             noplaylist=True,overwrites=False,continuedl=True,noprogress=True,
             retries=1,extractor_retries=1,socket_timeout=20,proxy=a.proxy,
             js_runtimes={'node':{'path':r'C:\Program Files\nodejs\node.exe'}})
try:
    with YoutubeDL(options) as ydl:
        info=ydl.extract_info(approval['url'],download=True)
        assert info['id']==approval['video_id'] and info.get('height',0)>360
        file=Path(ydl.prepare_filename(info));assert file.is_file()
    r.update(result='downloaded',file=file.name,sha256=sha(file),width=info['width'],height=info['height'],
             format_id=info['format_id'],fps=info.get('fps'),codec=info.get('vcodec'),
             meaning='Original encoded picture stream. Does not establish AV offset, exact RPM or start phase timing')
except Exception as exc:r.update(result='failed',error=str(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(r,ensure_ascii=False))
