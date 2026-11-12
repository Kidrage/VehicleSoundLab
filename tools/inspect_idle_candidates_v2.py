"""Read public watch-page metadata only; no video/audio/thumbnail download."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import urllib.request
sys.stdout.reconfigure(encoding='utf-8')

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--searched',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
shutil.copy2(__file__,a.out/'executed_inspect.py')
search=json.loads((a.searched/'report.json').read_text(encoding='utf-8'))
found={x['id']:x for s in search['searches'].values() for x in s.get('candidates',[])}
selected=['XZCOsnPYre0','cMuqS9x-Z1Y','QUWTsk9crlo']
assert all(key in found for key in selected)


def fetch(key):
    row=found[key]|dict(media_downloaded=False,local_audio_review=False,local_visual_review=False)
    try:
        request=urllib.request.Request(row['url'],headers={'User-Agent':'Mozilla/5.0','Accept-Language':'en-US,en;q=0.9'})
        with urllib.request.urlopen(request,timeout=25) as response:
            raw=response.read(12_000_000)
        path=a.out/f'{key}.html';path.write_bytes(raw)
        text=raw.decode('utf-8')
        match=re.search(r'(?:var\s+)?ytInitialPlayerResponse\s*=\s*',text)
        if not match:raise ValueError('No public player metadata')
        data=json.JSONDecoder().raw_decode(text[match.end():])[0]
        detail=data.get('videoDetails',{})
        assert detail.get('videoId')==key
        row.update(title=detail.get('title'),channel=detail.get('author'),
            seconds=int(detail.get('lengthSeconds',0)),description=detail.get('shortDescription'),
            playability=data.get('playabilityStatus',{}).get('status'),
            source_page=path.name,page_sha256=hashlib.sha256(raw).hexdigest(),result='metadata_only')
    except Exception as exc:row.update(result='failed',error=repr(exc))
    return row


with ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(fetch,selected))
r=dict(schema='vsl.idle-candidate-inspection/2',created_utc=datetime.now(timezone.utc).isoformat(),
    search_report_sha256=hashlib.sha256((a.searched/'report.json').read_bytes()).hexdigest(),
    candidates=rows,media_downloaded=False)
(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for row in rows:print(json.dumps(row,ensure_ascii=False),flush=True)
