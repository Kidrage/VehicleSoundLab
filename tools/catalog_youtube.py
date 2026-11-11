"""Extract public video metadata from saved search HTML. Downloads NO media."""
import json
import re
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
root=Path(__file__).resolve().parents[1]

def text(value):
    if isinstance(value,str):return value
    if not isinstance(value,dict):return ''
    return value.get('simpleText') or ''.join(r.get('text','') for r in value.get('runs',[])) or value.get('content','')

def walk(obj):
    if isinstance(obj,dict):
        if 'videoRenderer' in obj:
            v=obj['videoRenderer']
            yield dict(id=v.get('videoId'),title=text(v.get('title')),channel=text(v.get('ownerText')),
                duration=text(v.get('lengthText')),description=text(v.get('descriptionSnippet')),
                source='videoRenderer')
        if 'lockupViewModel' in obj:
            v=obj['lockupViewModel']
            if v.get('contentType')=='LOCKUP_CONTENT_TYPE_VIDEO':
                metadata=v.get('metadata',{}).get('lockupMetadataViewModel',{})
                rows=metadata.get('metadata',{}).get('contentMetadataViewModel',{}).get('metadataRows',[])
                yield dict(id=v.get('contentId'),title=text(metadata.get('title')),
                    channel=' | '.join(text(p.get('text')) for row in rows[:1] for p in row.get('metadataParts',[])),
                    duration='',description='',source='lockupViewModel')
        for value in obj.values():yield from walk(value)
    elif isinstance(obj,list):
        for value in obj:yield from walk(value)

catalog=[]
for kind in ('v10','911'):
    file=root/f'research/youtube_{kind}_full.html'
    if not file.exists():continue
    raw=file.read_text(encoding='utf-8')
    match=re.search(r'(?:var\s+)?ytInitialData\s*=\s*',raw)
    if not match:
        print('No initial metadata:',file.name);continue
    try:data=json.JSONDecoder().raw_decode(raw[match.end():])[0]
    except json.JSONDecodeError:
        print('Incomplete HTML:',file.name);continue
    seen=set()
    for v in walk(data):
        if not v['id'] or v['id'] in seen:continue
        seen.add(v['id']); v.update(category=kind,url='https://www.youtube.com/watch?v='+v['id'],approved=False)
        catalog.append(v);print(json.dumps(v,ensure_ascii=False))
(root/'research/video_search_catalog.json').write_text(json.dumps(catalog,indent=2,ensure_ascii=False),encoding='utf-8')
