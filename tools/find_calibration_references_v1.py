"""Public page metadata only. No audio, video, thumbnails or source cleaning."""
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime,timezone
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/calibration_candidates_v1'
QUERIES=[
    'Lamborghini Huracan Performante stock dyno RPM',
    'Lamborghini Huracan stock dyno sound rpm gauge',
    'Lamborghini Huracan Performante factory exhaust dyno run',
]
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36'
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept-Language':'en-US,en;q=0.8'})
    with urllib.request.urlopen(req,timeout=30) as r:return r.read().decode('utf-8')
def text(v):
    if isinstance(v,str):return v
    if not isinstance(v,dict):return ''
    return v.get('simpleText') or ''.join(r.get('text','') for r in v.get('runs',[])) or v.get('content','')
def walk(obj):
    if isinstance(obj,dict):
        if 'videoRenderer' in obj:
            v=obj['videoRenderer']
            yield dict(id=v.get('videoId'),title=text(v.get('title')),channel=text(v.get('ownerText')),
                duration=text(v.get('lengthText')),description=text(v.get('descriptionSnippet')))
        if 'lockupViewModel' in obj:
            v=obj['lockupViewModel'];m=v.get('metadata',{}).get('lockupMetadataViewModel',{})
            if v.get('contentType')=='LOCKUP_CONTENT_TYPE_VIDEO':
                rows=m.get('metadata',{}).get('contentMetadataViewModel',{}).get('metadataRows',[])
                yield dict(id=v.get('contentId'),title=text(m.get('title')),
                    channel=' | '.join(text(p.get('text')) for row in rows[:1] for p in row.get('metadataParts',[])),
                    duration='',description='')
        for value in obj.values():yield from walk(value)
    elif isinstance(obj,list):
        for value in obj:yield from walk(value)
def initial(raw,key):
    m=re.search(r'(?:var\s+)?'+key+r'\s*=\s*',raw)
    return json.JSONDecoder().raw_decode(raw[m.end():])[0] if m else None
def main():
    if (OUT/'search_catalog.json').exists():raise SystemExit('Preserve completed calibration_candidates_v1; use a new research folder.')
    OUT.mkdir(parents=True,exist_ok=True)
    catalog={};searches=[]
    for index,query in enumerate(QUERIES):
        url='https://www.youtube.com/results?'+urllib.parse.urlencode({'search_query':query})
        page=OUT/f'search_{index+1}.html'
        raw=page.read_text(encoding='utf-8') if page.exists() else get(url)
        if not page.exists():page.write_text(raw,encoding='utf-8')
        data=initial(raw,'ytInitialData');assert data is not None
        ids=[]
        for row in walk(data):
            if not row['id']:continue
            video_id=row['id'];ids.append(video_id)
            if video_id not in catalog:catalog[video_id]=dict(**row,url='https://www.youtube.com/watch?v='+video_id,queries=[])
            catalog[video_id]['queries'].append(query)
        searches.append(dict(query=query,url=url,ids=list(dict.fromkeys(ids))))
    result=dict(retrieved_utc=datetime.now(timezone.utc).isoformat(),media_downloaded=False,approved=False,
        searches=searches,candidates=list(catalog.values()))
    (OUT/'search_catalog.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    for row in result['candidates']:
        print(json.dumps({k:v for k,v in row.items() if k!='queries'},ensure_ascii=False))
if __name__=='__main__':main()
