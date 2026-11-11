import json
import re
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
root=Path(__file__).resolve().parents[1]
found=[]
for letter in 'ABC':
    path=root/f'research/candidate_{letter}_page.html'
    raw=path.read_text(encoding='utf-8')
    m=re.search(r'ytInitialPlayerResponse\s*=\s*',raw)
    if not m:
        print(letter,'No player metadata',len(raw));continue
    try:p=json.JSONDecoder().raw_decode(raw[m.end():])[0]
    except json.JSONDecodeError: print(letter,'Truncated');continue
    v=p.get('videoDetails',{}); micro=p.get('microformat',{}).get('playerMicroformatRenderer',{})
    info=dict(candidate=letter,video_id=v.get('videoId'),title=v.get('title'),channel=v.get('author'),
        seconds=v.get('lengthSeconds'),description=v.get('shortDescription'),
        publish_date=micro.get('publishDate'),playability=p.get('playabilityStatus',{}).get('status'),approved=False)
    found.append(info)
    print(json.dumps(info,ensure_ascii=False,indent=2))
(root/'research/candidate_metadata.json').write_text(json.dumps(found,ensure_ascii=False,indent=2),encoding='utf-8')
