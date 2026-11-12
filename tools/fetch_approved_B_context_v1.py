"""Ordinary context video or alignment audio retrieval for approved source B."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--proxy')
p.add_argument('--resume-from', type=Path)
p.add_argument('--media', choices=['context','alignment'], default='context')
a = p.parse_args()
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
from yt_dlp import YoutubeDL
from yt_dlp.version import __version__
from drive_evidence_v1.sources import sha

a.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, a.out/'executed_fetch.py')
catalog = a.workspace/'references/segments_v1.json'
entry = json.loads(catalog.read_text(encoding='utf-8'))['sources']['B']
assert entry['url'] == 'https://www.youtube.com/watch?v=qmp1SVhmXgU'
assert 'Approved by user' in entry['approval']
r = dict(schema='vsl.approved-b-context-fetch/1', result='running',
         started_utc=datetime.now(timezone.utc).isoformat(),
         source_sha256=sha(Path(__file__)), catalog_sha256=sha(catalog),
         url=entry['url'], approval=entry['approval'], yt_dlp_version=__version__,
         cookies_or_account_used=False, audio_master_modified=False,
         media=a.media,
         proxy='existing local HTTP proxy' if a.proxy else 'default network')
if a.resume_from:
    assert a.media == 'context'
    previous = a.resume_from.resolve(strict=True)
    previous.relative_to((a.workspace/'references/analysis').resolve())
    old = json.loads((previous/'report.json').read_text(encoding='utf-8'))
    assert old['url'] == entry['url'] and old['result'] == 'retrieval_failed'
    info_path = previous/'B_context_qmp1SVhmXgU.info.json'
    info_old = json.loads(info_path.read_text(encoding='utf-8'))
    assert info_old['id'] == 'qmp1SVhmXgU' and info_old['format_id'] == '398'
    partial = previous/'B_context_qmp1SVhmXgU.mp4.part'
    assert partial.is_file()
    partial_sha = sha(partial)
    shutil.copy2(partial, a.out/partial.name)
    assert sha(a.out/partial.name) == partial_sha
    r['resumed_copy'] = dict(previous_report_sha256=sha(previous/'report.json'),
        previous_metadata_sha256=sha(info_path), partial_sha256=partial_sha,
        bytes=partial.stat().st_size, original_partial_preserved=True)
log = (a.out/'download.log').open('w', encoding='utf-8', newline='\n')


class Logger:
    def debug(self, message):
        log.write(message+'\n'); log.flush()
    info = debug
    warning = debug
    error = debug


try:
    choice = 'bestvideo[height<=720]/best[height<=720]' if a.media == 'context' else 'bestaudio[ext=m4a]/bestaudio'
    options = dict(format=choice,
        outtmpl=str(a.out/('B_'+a.media+'_%(id)s.%(ext)s')), noplaylist=True,
        retries=1, extractor_retries=0, fragment_retries=0, socket_timeout=30,
        js_runtimes={'node': {'path': r'C:\Program Files\nodejs\node.exe'}},
        ffmpeg_location=r'D:\repo\tools\ffmpeg\bin',
        overwrites=False, continuedl=True, noprogress=True, writeinfojson=True,
        logger=Logger(), proxy=a.proxy)
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(entry['url'], download=True)
        assert info['id'] == 'qmp1SVhmXgU'
        file = Path(ydl.prepare_filename(info))
        assert file.is_file()
    r.update(result='downloaded_video_context_not_aligned' if a.media=='context' else 'downloaded_audio_not_aligned', file=str(file),
             sha256=sha(file), title=info.get('title'), channel=info.get('channel'),
             duration_seconds=info.get('duration'), format_id=info.get('format_id'),
             width=info.get('width'), height=info.get('height'),
             limits=['Existing user MP3 alignment has not been measured',
                     'Video not yet inspected; no RPM, gear, load or idle inference'])
except Exception as exc:
    r.update(result='retrieval_failed', error=str(exc))
finally:
    log.close()
    r['finished_utc'] = datetime.now(timezone.utc).isoformat()
    (a.out/'report.json').write_text(json.dumps(r, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(r, ensure_ascii=False), flush=True)
