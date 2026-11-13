"""Coarse original-PTS pictures for human state review; no telemetry inference."""
from fractions import Fraction
import math
import re
import subprocess
from PIL import Image, ImageDraw, ImageOps


def context_frames(media, directory, stream, duration, count, ffmpeg):
    rate = float(Fraction(stream['r_frame_rate']))
    targets = [round((i+.5)*duration/count*rate) for i in range(count)]
    selection = '+'.join('eq(n,'+str(index)+')' for index in targets)
    command = [str(ffmpeg), '-hide_banner', '-nostdin', '-threads', '2', '-i', str(media),
        '-an', '-vf', "select='"+selection+"',scale=480:-2,showinfo", '-fps_mode', 'vfr',
        '-q:v', '2', str(directory/'frame_%03d.jpg')]
    result = subprocess.run(command, capture_output=True, check=True)
    (directory/'frame_log.txt').write_bytes(result.stderr)
    matches = re.findall(r'\bn:\s*(\d+) pts:\s*(-?\d+) pts_time:([-\d.]+)',
                         result.stderr.decode('utf-8', errors='replace'))
    rows = [dict(file='frame_'+str(int(n)+1).zfill(3)+'.jpg', pts=int(pts),
                 source_pts_seconds=float(int(pts)*Fraction(stream['time_base'])))
            for n, pts, _ in matches]
    assert len(rows) == count and all((directory/row['file']).is_file() for row in rows)
    board = Image.new('RGB', (1280, math.ceil(count/4)*208), '#151b22')
    draw = ImageDraw.Draw(board)
    for index, row in enumerate(rows):
        x, y = index%4*320, index//4*208
        with Image.open(directory/row['file']) as original:
            thumb = ImageOps.contain(original, (320, 180))
            board.paste(thumb, (x+(320-thumb.width)//2, y+(180-thumb.height)//2))
        draw.text((x+6, y+184), f"{row['source_pts_seconds']:.3f} s | original PTS", fill='white')
    board.save(directory/'context.jpg', quality=95)
    return dict(command=command, requested_frame_indices=targets, frames=rows,
                limits=['Coarse frames cannot establish intervening actions or calibrated AV offset',
                        'No RPM, gear, temperature, pedal or physical load label inferred automatically'])
