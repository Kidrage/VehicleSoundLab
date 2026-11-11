"""Download only audio explicitly approved in the workspace manifest.

Uses ordinary yt-dlp extraction; no browser cookies or account access.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/python_deps'))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('ids',nargs='+'); p.add_argument('--proxy')
    a=p.parse_args()
    catalog=json.loads((ROOT/'references/approval_manifest.json').read_text(encoding='utf-8'))
    selected=[]
    for identity in a.ids:
        item=next((v for v in catalog if v['id']==identity),None)
        if not item or item.get('approved') is not True or not item.get('approval_evidence'):
            p.error(f'{identity} has no user approval. Nothing downloaded.')
        selected.append(item)
    from yt_dlp import YoutubeDL
    raw=ROOT/'references/raw'; raw.mkdir(parents=True,exist_ok=True)
    for item in selected:
        options=dict(format='bestaudio',noplaylist=True,retries=2,extractor_retries=1,
            socket_timeout=25,js_runtimes={'node':{}},
            outtmpl=str(raw/f"{item['id']}_%(id)s.%(ext)s"),
            writeinfojson=True,overwrites=False,proxy=a.proxy,
            ffmpeg_location=r'D:\repo\tools\ffmpeg\bin')
        with YoutubeDL(options) as ydl:
            info=ydl.extract_info(item['url'],download=True)
            filename=Path(ydl.prepare_filename(info))
        h=hashlib.sha256()
        with filename.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        provenance=dict(source_id=item['id'],url=item['url'],video_id=info['id'],
            title=info.get('title'),channel=info.get('channel'),duration_seconds=info.get('duration'),
            original_file=filename.name,sha256=h.hexdigest(),format_id=info.get('format_id'),
            codec=info.get('acodec'),sample_rate=info.get('asr'),
            approval_evidence=item['approval_evidence'],downloaded_at_utc=datetime.now(timezone.utc).isoformat(),
            chapters=info.get('chapters'),description=info.get('description'))
        (raw/f"{item['id']}_provenance.json").write_text(json.dumps(provenance,indent=2,ensure_ascii=False),encoding='utf-8')
        print('Saved approved source',item['id'],filename.name,'SHA256',h.hexdigest())

if __name__=='__main__':main()
