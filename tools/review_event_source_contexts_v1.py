"""Original approved-media context for unclassified transients; no event labeling."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


CASES = (
    ('A_rear_213', 'A', 213.4), ('A_rear_249', 'A', 248.875),
    ('A_drive_319', 'A', 318.77), ('A_drive_335', 'A', 335.435),
    ('B_intro_12', 'B', 11.565), ('B_end_815', 'B', 814.63),
    ('D_late_55', 'D', 55.445), ('E_drive_79', 'E', 78.935),
    ('F3_103', 'F3', 103.465), ('F3_182', 'F3', 181.52),
)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--data-root', type=Path, default=Path('E:/VehicleSoundLab'))
    p.add_argument('--ffmpeg', default='D:/repo/tools/ffmpeg/bin/ffmpeg.exe')
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(a.data_root/'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    from PIL import Image, ImageDraw, ImageFont
    from event_authoring.audio import sha
    from event_authoring.measure import observe
    repo = Path(__file__).resolve().parents[1]
    manifest = json.loads((repo/'references/segments_v1.json').read_text(encoding='utf-8'))
    approvals = {r['id']:r['approved'] for r in json.loads((a.data_root/'references/approval_manifest.json').read_text(encoding='utf-8'))}
    sources = {}
    for identity in sorted(set(row[1] for row in CASES)):
        if not approvals.get(identity):
            raise ValueError('Source is not approved: ' + identity)
        entry = manifest['sources'][identity]
        path = a.data_root/entry['master']
        identity_hash = sha(path)
        if identity_hash != entry['master_sha256']:
            raise ValueError('Master identity changed: ' + identity)
        video = a.data_root/entry['video']
        if sha(video) != entry['video_sha256']:
            raise ValueError('Video identity changed: ' + identity)
        sources[identity] = dict(audio=str(path), audio_sha256=identity_hash,
            video=str(video), video_sha256=entry['video_sha256'], url=entry['url'],
            audio_to_video_seconds=.036291667 if identity == 'B' else 0.)

    def read(path, first, last):
        with sf.SoundFile(path) as stream:
            if stream.samplerate != 48000:
                raise ValueError('Use an explicitly decoded 48 kHz master')
            stream.seek(round(first*48000))
            x = stream.read(round(last*48000)-round(first*48000), dtype='float64', always_2d=True)
            if not np.isfinite(x).all():
                raise ValueError('Nonfinite source data')
            return x

    def one(case):
        name, identity, at = case
        source = sources[identity]
        folder = a.output/name
        folder.mkdir()
        first, last = at-1., at+1.5
        audio = read(source['audio'], first, last)
        # The original reference remains untouched; the monitor copy has only a
        # common quarter gain, identical across contexts, without fades/EQ.
        sf.write(folder/'original.wav', audio, 48000, subtype='FLOAT')
        sf.write(folder/'monitor.wav', audio*.25, 48000, subtype='FLOAT')
        event_range, background_range = [at-.035, at+.16], [at-.55, at-.25]
        measured, _ = observe(read(source['audio'], *event_range), read(source['audio'], *background_range))
        seek = at + source['audio_to_video_seconds']
        command = [a.ffmpeg, '-hide_banner', '-loglevel', 'error', '-ss', str(seek),
                   '-i', source['video'], '-frames:v', '1', '-vf', 'scale=480:-2',
                   '-y', str(folder/'context.jpg')]
        subprocess.run(command, capture_output=True, text=True, check=True)
        value = dict(name=name, source_id=identity, candidate_seconds=at,
            context_seconds=[first, last], event_measurement_seconds=event_range,
            background_measurement_seconds=background_range, measurement=measured,
            source=source, requested_video_seek_seconds=seek,
            classification='unclassified acoustic transient', physical_identity_confirmed=False,
            original_pcm_sha256=hashlib.sha256(audio.astype('<f4').tobytes()).hexdigest(),
            monitor_gain=.25, additional_processing=False)
        (folder/'context.json').write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        return value

    with ThreadPoolExecutor(max_workers=3) as executor:
        rows = list(executor.map(one, CASES))
    font = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 17)
    sheet = Image.new('RGB', (1000, 5*330), '#f2f4f7')
    draw = ImageDraw.Draw(sheet)
    for index, row in enumerate(rows):
        col, line = index % 2, index // 2
        photo = Image.open(a.output/row['name']/'context.jpg').convert('RGB')
        photo.thumbnail((480, 270))
        x, y = 10+col*500, 10+line*330
        sheet.paste(photo, (x, y))
        draw.text((x, y+274), f"{row['name']} | source {row['candidate_seconds']:.3f}s", fill='#172338', font=font)
        draw.text((x, y+298), f"Full-band contrast {row['measurement']['event_to_background_db']:+.2f} dB", fill='#53647b', font=font)
    sheet.save(a.output/'contexts.jpg')
    report = dict(schema='vsl.event-source-context-review/1', cases=rows,
        limits=['These are candidates from a fixed detector, not classified afterfires.',
                'Local contrast can include speech, edits, shifts, tire and recording artifacts.',
                'Video seek is context only; combustion/ECU/display timing is not calibrated.',
                'No fit, cleaning, physical source separation, new download or global event-bank change.'],
        detector_report=str(a.data_root/'references/analysis/event_sources_v1/inspect1/report.json'),
        script_sha256=sha(__file__))
    (a.output/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    shutil.copy2(__file__, a.output/'executed_review.py')
    print(json.dumps([dict(name=r['name'], contrast_db=r['measurement']['event_to_background_db']) for r in rows]), flush=True)


if __name__ == '__main__':
    main()
