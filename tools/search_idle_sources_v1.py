"""Find public idle/calibration candidates. Fetch HTML metadata only, no media."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import urlencode
import urllib.request
sys.stdout.reconfigure(encoding='utf-8')

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
shutil.copy2(__file__,a.out/'executed_search.py')
queries=[('idle','Lamborghini Huracan stock exhaust warm idle pure sound'),
         ('tach','Lamborghini Huracan idle revs tachometer'),
         ('pull','Lamborghini Huracan acceleration low rpm single gear pure sound')]


def text(value):
    if isinstance(value,str):return value
    if not isinstance(value,dict):return ''
    return value.get('simpleText') or ''.join(x.get('text','') for x in value.get('runs',[])) or value.get('content','')


def videos(obj):
    if isinstance(obj,dict):
        if 'videoRenderer' in obj:
            v=obj['videoRenderer']
            yield dict(id=v.get('videoId'),title=text(v.get('title')),channel=text(v.get('ownerText')),
                       duration=text(v.get('lengthText')),description=text(v.get('descriptionSnippet')))
        if 'lockupViewModel' in obj:
            v=obj['lockupViewModel']
            if v.get('contentType')=='LOCKUP_CONTENT_TYPE_VIDEO':
                m=v.get('metadata',{}).get('lockupMetadataViewModel',{})
                rows=m.get('metadata',{}).get('contentMetadataViewModel',{}).get('metadataRows',[])
                yield dict(id=v.get('contentId'),title=text(m.get('title')),
                    channel=' | '.join(text(x.get('text')) for row in rows[:1] for x in row.get('metadataParts',[])),duration='')
        for v in obj.values():yield from videos(v)
    elif isinstance(obj,list):
        for v in obj:yield from videos(v)


def fetch(item):
    name,query=item
    url='https://www.youtube.com/results?'+urlencode(dict(search_query=query))
    row=dict(query=query,url=url,approved=False,media_downloaded=False)
    try:
        request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept-Language':'en-US,en;q=0.9'})
        with urllib.request.urlopen(request,timeout=25) as response:
            raw=response.read(12_000_000).decode('utf-8')
        (a.out/f'{name}.html').write_text(raw,encoding='utf-8')
        match=re.search(r'(?:var\s+)?ytInitialData\s*=\s*',raw)
        if not match:raise ValueError('No public search initial data')
        data=json.JSONDecoder().raw_decode(raw[match.end():])[0]
        seen=set();rows=[]
        for video in videos(data):
            if video.get('id') and video['id'] not in seen:
                seen.add(video['id']);rows.append(video|dict(url='https://www.youtube.com/watch?v='+video['id'],approved=False,media_downloaded=False))
        row.update(result='metadata_only',candidates=rows)
    except Exception as exc:row.update(result='failed',error=repr(exc))
    return name,row


with ThreadPoolExecutor(max_workers=3) as pool:results=dict(pool.map(fetch,queries))
report=dict(schema='vsl.idle-source-search/1',created_utc=datetime.now(timezone.utc).isoformat(),
            searches=results,media_downloaded=False,approval_rule='Review before media retrieval or cleaning')
(a.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for name,row in results.items():print(json.dumps(dict(key=name,**row),ensure_ascii=False),flush=True)
