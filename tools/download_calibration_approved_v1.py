"""Download approved D/E audio and readable video with ordinary yt-dlp.
No browser cookies/account access; merged streams are copied, not re-encoded.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/python_deps'))
sys.stdout.reconfigure(encoding='utf-8')
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('identity',choices=['D','E']);parser.add_argument('--proxy')
    args=parser.parse_args()
    catalog=json.loads((ROOT/'references/approval_manifest.json').read_text(encoding='utf-8'))
    item=next(v for v in catalog if v['id']==args.identity)
    if not item.get('approved') or not item.get('approval_evidence'):parser.error('Explicit approval required')
    from yt_dlp import YoutubeDL
    from yt_dlp.version import __version__
    raw=ROOT/'references/raw';raw.mkdir(exist_ok=True)
    status=raw/f"{item['id']}_download_attempt_v1.json"
    if status.exists():parser.error('Preserve completed attempt; use a new attempt/version')
    provenance=raw/f"{item['id']}_provenance_v1.json"
    if provenance.exists():parser.error('Source already downloaded; inspect existing provenance')
    attempt=dict(source_id=item['id'],video_id=item['video_id'],url=item['url'],
        approval_evidence=item['approval_evidence'],started_utc=datetime.now(timezone.utc).isoformat(),
        yt_dlp_version=__version__,proxy='existing local HTTP proxy' if args.proxy else 'default network',
        browser_cookies_used=False)
    options=dict(format='bestvideo[height<=1080]+bestaudio/best[height<=1080]',noplaylist=True,
        retries=1,extractor_retries=1,socket_timeout=20,js_runtimes={'node':{'path':r'C:\Program Files\nodejs\node.exe'}},
        ffmpeg_location=r'D:\repo\tools\ffmpeg\bin',merge_output_format='mkv',
        outtmpl=str(raw/f"{item['id']}_%(id)s.%(ext)s"),writeinfojson=True,overwrites=False,
        continuedl=True,noprogress=True,proxy=args.proxy)
    try:
        with YoutubeDL(options) as ydl:
            info=ydl.extract_info(item['url'],download=True)
            requested=info.get('requested_downloads') or []
            file=Path(requested[0]['filepath']) if requested and requested[0].get('filepath') else Path(ydl.prepare_filename(info))
            if not file.exists():file=raw/f"{item['id']}_{item['video_id']}.mkv"
        if not file.is_file():raise RuntimeError('Merged source not found')
        if info['id']!=item['video_id']:raise RuntimeError('Wrong video identity')
        result=dict(source_id=item['id'],url=item['url'],video_id=info['id'],title=info.get('title'),
            channel=info.get('channel'),duration_seconds=info.get('duration'),
            raw_file=file.relative_to(ROOT).as_posix(),sha256=sha(file),
            format_id=info.get('format_id'),width=info.get('width'),height=info.get('height'),
            fps=info.get('fps'),acodec=info.get('acodec'),vcodec=info.get('vcodec'),
            requested_formats=[{k:v.get(k) for k in ['format_id','ext','acodec','vcodec','asr','audio_channels','width','height','fps']} for v in info.get('requested_formats',[])],
            approval_evidence=item['approval_evidence'],downloaded_utc=datetime.now(timezone.utc).isoformat(),
            processing='Original encoded streams, copied into MKV by ffmpeg; no audio/video filtering',
            not_established=['RPM readings','load/pedal telemetry','recording perspective','stock exhaust','audio quality','A/V alignment'])
        provenance.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        attempt.update(status='downloaded',file=result['raw_file'],sha256=result['sha256'])
        print(json.dumps(result,ensure_ascii=False),flush=True)
    except Exception as exc:
        attempt.update(status='failed',error=str(exc));raise
    finally:
        attempt['finished_utc']=datetime.now(timezone.utc).isoformat()
        status.write_text(json.dumps(attempt,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
