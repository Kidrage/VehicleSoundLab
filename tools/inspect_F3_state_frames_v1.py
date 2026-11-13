"""Original-resolution, original-PTS context around F3 idle/launch/acceleration candidates."""
import argparse
from fractions import Fraction
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
from PIL import Image, ImageDraw, ImageOps
from drive_evidence_v1.sources import sha

args.out.resolve().relative_to((args.workspace/'references/analysis').resolve())
args.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, args.out/'executed_inspect.py')
fetch_path = args.workspace/'references/raw/state_media_v1/F3_fetch2/report.json'
fetch = json.loads(fetch_path.read_text(encoding='utf-8'))
assert fetch['identity'] == 'F3' and fetch['result'] == 'downloaded_for_usability_inspection'
media = args.workspace/fetch['file']
assert sha(media) == fetch['sha256']
probe = json.loads((fetch_path.parent/'ffprobe.json').read_text(encoding='utf-8'))
stream = next(row for row in probe['streams'] if row['codec_type'] == 'video')
time_base = Fraction(stream['time_base'])
windows = dict(cabin_stationary_candidate=list(range(40, 66, 5)),
               launch_candidate=list(range(100, 117)),
               motorway1=list(range(150, 171)), motorway2=list(range(184, 205)))
report = dict(schema='vsl.F3-state-frames/1', result='running', input_sha256=sha(media),
    fetch_report_sha256=sha(fetch_path), source_sha256=sha(Path(__file__)),
    stream=stream, windows=windows, observations={}, audio_read=False,
    model_extracted=False, runtime_changed=False, timbre_accepted=False)
try:
    for name, targets in windows.items():
        out = args.out/name
        out.mkdir()
        pts_targets = [int(Fraction(t)/time_base) for t in targets]
        select = '+'.join('eq(pts,'+str(pts)+')' for pts in pts_targets)
        command = [r'D:\repo\tools\ffmpeg\bin\ffmpeg.exe', '-hide_banner', '-nostdin',
            '-ss', str(targets[0]-1), '-copyts', '-threads', '2', '-i', str(media), '-an',
            '-vf', "select='"+select+"',showinfo", '-frames:v', str(len(targets)),
            '-fps_mode', 'vfr', '-q:v', '2', str(out/'frame_%03d.jpg')]
        done = subprocess.run(command, capture_output=True, check=True)
        (out/'frame_log.txt').write_bytes(done.stderr)
        pairs = re.findall(r'\bn:\s*(\d+) pts:\s*(-?\d+) pts_time:([-\d.]+)',
                           done.stderr.decode('utf-8', errors='replace'))
        assert [int(pts) for _, pts, _ in pairs] == pts_targets
        rows = []
        for n, pts, _ in pairs:
            path = out/('frame_'+str(int(n)+1).zfill(3)+'.jpg')
            rows.append(dict(file=path.name, sha256=sha(path), pts=int(pts),
                             source_pts_seconds=float(int(pts)*time_base)))
        sheet = Image.new('RGB', (1600, math.ceil(len(rows)/4)*250), '#151b22')
        draw = ImageDraw.Draw(sheet)
        for i, row in enumerate(rows):
            x, y = i%4*400, i//4*250
            with Image.open(out/row['file']) as picture:
                thumb = ImageOps.contain(picture, (400, 225))
                sheet.paste(thumb, (x+(400-thumb.width)//2, y+(225-thumb.height)//2))
            draw.text((x+6, y+230), f"{row['source_pts_seconds']:.3f} s | original PTS", fill='white')
        sheet.save(out/'context.jpg', quality=95)
        report['observations'][name] = dict(command=command, frames=rows, sheet_sha256=sha(out/'context.jpg'))
        print(json.dumps(dict(window=name, frames=len(rows))), flush=True)
    report.update(result='original_PTS_state_frames_prepared', visual_review_completed=False,
        limits=['No audio processing, phase estimate or RPM-to-sound alignment',
            'Sampled video is state evidence, not continuous pedal/load/temperature telemetry',
            'An instrument graphic may have editorial latency relative to source audio'])
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n',
                                      encoding='utf-8', newline='\n')
