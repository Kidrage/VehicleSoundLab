"""Retrieve approved F1/F2/F3 encoded streams, preserving each attempt and provenance."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--identity', choices=('F1', 'F2', 'F3'), required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--proxy')
    parser.add_argument('--resume-from', type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    from drive_evidence_v1.sources import sha
    from yt_dlp import YoutubeDL
    from yt_dlp.version import __version__

    plan_path = repo/'research/approved_state_media_v1_plan.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    selected = next(row for row in plan['sources'] if row['id'] == args.identity)
    catalog_path = args.workspace/'references/approval_manifest.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    entry = next(row for row in catalog if row['id'] == args.identity)
    assert selected['approved'] is True and entry['approved'] is True
    assert entry['video_id'] == selected['video_id'] and entry['url'] == selected['url']
    assert entry['approval_evidence'] == plan['approval_evidence']
    args.out.resolve().relative_to((args.workspace/'references').resolve())
    args.out.mkdir(parents=True, exist_ok=False)
    for source, name in ((Path(__file__), 'executed_fetch.py'),
                         (plan_path, 'approved_plan.json'), (catalog_path, 'approval_manifest.json')):
        shutil.copy2(source, args.out/name)
    report = dict(schema='vsl.approved-state-media-fetch/1', result='running',
        started_utc=datetime.now(timezone.utc).isoformat(), identity=args.identity,
        video_id=entry['video_id'], url=entry['url'], approval_evidence=entry['approval_evidence'],
        sources={str(p.relative_to(repo)).replace('\\', '/'): sha(p) for p in (Path(__file__), plan_path)},
        approval_manifest_sha256=sha(catalog_path), yt_dlp_version=__version__,
        proxy='existing local HTTP proxy' if args.proxy else 'default network',
        browser_cookies_or_account_used=False, audio_filtering=False, audio_normalized=False,
        real_model_extracted=False, runtime_changed=False, timbre_accepted=False)
    selected_format = plan['retrieval']['format']
    if args.resume_from:
        previous = args.resume_from.resolve(strict=True)
        previous.relative_to((args.workspace/'references').resolve())
        old = json.loads((previous/'report.json').read_text(encoding='utf-8'))
        assert old['identity'] == args.identity and old['video_id'] == entry['video_id']
        assert old['result'] == 'retrieval_failed'
        metadata = previous/(args.identity+'_'+entry['video_id']+'.info.json')
        old_info = json.loads(metadata.read_text(encoding='utf-8'))
        assert old_info['id'] == entry['video_id']
        selected_format = old_info['format_id']
        resumed = []
        for source in sorted(previous.glob(args.identity+'_'+entry['video_id']+'*')):
            if source.suffix not in ('.part', '.ytdl', '.json'):
                continue
            digest = sha(source)
            shutil.copy2(source, args.out/source.name)
            assert sha(args.out/source.name) == digest
            resumed.append(dict(file=source.name, bytes=source.stat().st_size, sha256=digest))
        assert any(row['file'].endswith('.part') for row in resumed)
        report['resumed_copy'] = dict(previous_report_sha256=sha(previous/'report.json'),
            selected_format=selected_format, files=resumed, original_attempt_preserved=True)
    log = (args.out/'download.log').open('w', encoding='utf-8', newline='\n')

    class Logger:
        def debug(self, message):
            log.write(message+'\n')
            log.flush()
        info = debug
        warning = debug
        error = debug

    try:
        options = dict(format=selected_format, noplaylist=True,
            retries=1, extractor_retries=1, fragment_retries=1, socket_timeout=20,
            js_runtimes={'node': {'path': r'C:\Program Files\nodejs\node.exe'}},
            ffmpeg_location=r'D:\repo\tools\ffmpeg\bin', merge_output_format='mkv',
            outtmpl=str(args.out/(args.identity+'_%(id)s.%(ext)s')),
            writeinfojson=True, overwrites=False, continuedl=True, noprogress=True,
            logger=Logger(), proxy=args.proxy)
        with YoutubeDL(options) as downloader:
            info = downloader.extract_info(entry['url'], download=True)
            assert info['id'] == entry['video_id']
            requested = info.get('requested_downloads') or []
            path = Path(requested[0]['filepath']) if requested and requested[0].get('filepath') else Path(downloader.prepare_filename(info))
            if not path.is_file():
                path = args.out/(args.identity+'_'+entry['video_id']+'.mkv')
            assert path.is_file(), 'Downloaded stream not found'
        probe_command = [r'D:\repo\tools\ffmpeg\bin\ffprobe.exe', '-v', 'error',
            '-show_streams', '-show_format', '-of', 'json', str(path)]
        probe = subprocess.run(probe_command, capture_output=True, text=True,
                               encoding='utf-8', check=True)
        probe_data = json.loads(probe.stdout)
        (args.out/'ffprobe.json').write_text(probe.stdout, encoding='utf-8')
        assert any(s['codec_type'] == 'audio' for s in probe_data['streams'])
        assert any(s['codec_type'] == 'video' for s in probe_data['streams'])
        report.update(result='downloaded_for_usability_inspection',
            file=path.relative_to(args.workspace).as_posix(), sha256=sha(path), bytes=path.stat().st_size,
            title=info.get('title'), channel=info.get('channel'), duration_seconds=info.get('duration'),
            description=info.get('description'), format_id=info.get('format_id'),
            requested_formats=[{k: v.get(k) for k in ('format_id', 'ext', 'acodec', 'vcodec',
                'asr', 'audio_channels', 'width', 'height', 'fps')} for v in info.get('requested_formats', [])],
            streams=[{k: v.get(k) for k in ('codec_type', 'codec_name', 'sample_rate', 'channels',
                'width', 'height', 'r_frame_rate', 'start_time', 'duration', 'bit_rate')} for v in probe_data['streams']],
            processing='Original encoded streams copied into MKV; no denoising, normalization or resampling',
            not_established=['Recording usability', 'music/speech contamination', 'stock exhaust',
                'actual idle temperature and RPM', 'load/pedal telemetry', 'AV synchronization', 'new timbre acceptance'])
    except Exception as exc:
        report.update(result='retrieval_failed', error=repr(exc))
    finally:
        log.close()
        report['finished_utc'] = datetime.now(timezone.utc).isoformat()
        (args.out/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n',
                                          encoding='utf-8', newline='\n')
    print(json.dumps({k: report.get(k) for k in ('identity', 'result', 'file', 'bytes', 'error')},
                     ensure_ascii=False), flush=True)
    return 0 if report['result'] == 'downloaded_for_usability_inspection' else 1


if __name__ == '__main__':
    raise SystemExit(main())
