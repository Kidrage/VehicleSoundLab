"""Exact decoded video frame PTS, with instrument crops for human annotation."""
from fractions import Fraction
import json
import re
import subprocess
from PIL import Image, ImageDraw, ImageFont
from .sources import sha


def observe(workspace, output, ffmpeg, step=15):
    catalog = json.loads((workspace / 'references/segments_v1.json').read_text(encoding='utf-8'))
    source = catalog['sources']['E']
    video = workspace / source['video']
    assert sha(video) == source['video_sha256']
    # Existing index contains exact PTS of every source frame. Reuse only after
    # checking the raw media identity; extraction itself decodes the raw file.
    index_path = workspace / 'references/analysis/DE_usability_v1/E/video_frames.json'
    index = json.loads(index_path.read_text(encoding='utf-8'))
    by_pts = {int(v['best_effort_timestamp']): i for i, v in enumerate(index['all_frames'])}
    base = Fraction(index['time_base'])
    selection = f"between(t,82,94)*not(mod(n,{step}))"
    command = [str(ffmpeg), '-v', 'info', '-nostdin', '-n', '-to', '94.1', '-i', str(video),
        '-vf', f"select='{selection}',crop=1280:600:100:180,showinfo", '-fps_mode', 'vfr', str(output / 'frame_%03d.png')]
    run = subprocess.run(command, check=True, capture_output=True)
    (output / 'decode.log').write_bytes(run.stderr)
    parsed = re.findall(r'\bn:\s*(\d+) pts:\s*(\d+) pts_time:([\d.]+)', run.stderr.decode('utf-8', errors='replace'))
    rows = []
    for number, pts, shown in parsed:
        pts = int(pts)
        seconds = float(pts * base)
        assert abs(seconds-float(shown)) < .001
        frame = output / f'frame_{int(number)+1:03d}.png'
        rows.append(dict(file=frame.name, source_frame_index=by_pts[pts], pts=pts,
            source_seconds=seconds, sha256=sha(frame)))
    assert rows and len(rows) == len(list(output.glob('frame_*.png')))
    sheets = []
    font = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 17)
    for first in range(0, len(rows), 8):
        subset = rows[first:first+8]
        board = Image.new('RGB', (1280, 330*((len(subset)+1)//2)), '#101922')
        draw = ImageDraw.Draw(board)
        for i, row in enumerate(subset):
            with Image.open(output / row['file']) as image:
                image = image.resize((640, 300))
                x, y = i%2*640, i//2*330
                board.paste(image, (x, y))
                draw.text((x+8, y+303), f"{row['source_seconds']:.3f}s | frame {row['source_frame_index']}", font=font, fill='white')
        path = output / f'sheet_{first//8+1:02d}.jpg'
        board.save(path, quality=95)
        sheets.append(path.name)
    result = dict(source='E', video=source['video'], video_sha256=sha(video),
        source_index_sha256=sha(index_path), time_base=index['time_base'], command=command,
        crop=[100, 180, 1280, 600], step_source_frames=step, frames=rows, sheets=sheets,
        limits='Video PTS, not measured A/V alignment or ECU timestamp. Crop and display resize only; no enhancement/OCR.')
    (output / 'frames.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result
