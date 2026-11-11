"""Read saved public watch pages; preserve claims separately from observations."""
import hashlib
import json
import re
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/calibration_candidates_v1'
def main():
    target=OUT/'watch_metadata.json'
    if target.exists():raise SystemExit('Preserve finished watch metadata.')
    rows=[]
    for file in sorted(OUT.glob('watch_*.html')):
        raw=file.read_text(encoding='utf-8');m=re.search(r'(?:var\s+)?ytInitialPlayerResponse\s*=\s*',raw)
        assert m is not None,file
        player=json.JSONDecoder().raw_decode(raw[m.end():])[0]
        video=player.get('videoDetails',{});micro=player.get('microformat',{}).get('playerMicroformatRenderer',{})
        row=dict(id=file.stem.removeprefix('watch_'),title=video.get('title'),channel=video.get('author'),
            seconds=video.get('lengthSeconds'),description=video.get('shortDescription'),
            publish_date=micro.get('publishDate'),playability=player.get('playabilityStatus',{}).get('status'),
            media_downloaded=False,approved=False,local_visual_review=False,local_audio_review=False,
            source_page=file.name,page_sha256=hashlib.sha256(file.read_bytes()).hexdigest())
        row['url']='https://www.youtube.com/watch?v='+row['id']
        assert row['id']==video.get('videoId'),row
        rows.append(row);print(json.dumps(row,ensure_ascii=False))
    target.write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf-8')
if __name__=='__main__':main()
