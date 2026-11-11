"""Approved A video-only context inspection, retaining exact decoded PTS."""
import json
import re
import subprocess
from fractions import Fraction
from runtime_review import ROOT, sha
from reference_segments import checked_source, CATALOG
from PIL import Image, ImageDraw

OUT = ROOT / 'references/analysis/state_context_v1'
FFMPEG = 'D:/repo/tools/ffmpeg/bin/ffmpeg.exe'
WINDOWS = {
    'low_scene_edge': [207.5, 213.5],
    'stationary_revs': [237.5, 248.5],
    'driving_scenes': [294.5, 320.5],
    'closing_edit': [330, 334],
}


def main():
    if (OUT/'verification.json').exists():
        raise SystemExit('Preserve completed state_context_v1 evidence.')
    OUT.mkdir(parents=True, exist_ok=True)
    source = checked_source('A')
    video = ROOT/source['video']
    assert sha(video) == source['video_sha256']
    stream = json.loads(subprocess.check_output([
        FFMPEG.replace('ffmpeg.exe', 'ffprobe.exe'), '-v', 'error',
        '-select_streams', 'v:0', '-show_entries',
        'stream=time_base,r_frame_rate,width,height,start_time,duration',
        '-of', 'json', str(video)]))['streams'][0]
    selection = '+'.join(f'between(t,{lo},{hi})' for lo,hi in WINDOWS.values())
    command = [FFMPEG, '-hide_banner', '-nostdin', '-y', '-to', '334.1',
        '-i', str(video), '-vf', f"select='({selection})*not(mod(n,15))',showinfo",
        '-fps_mode', 'vfr', '-q:v', '2', str(OUT/'frame_%03d.jpg')]
    done = subprocess.run(command, check=True, capture_output=True)
    (OUT/'frame_log.txt').write_bytes(done.stderr)
    rows = re.findall(r'\bn:\s*(\d+) pts:\s*(\d+) pts_time:([\d.]+)',
        done.stderr.decode('utf-8', errors='replace'))
    time_base = Fraction(stream['time_base'])
    frames = []
    for number,pts,shown in rows:
        t = float(int(pts)*time_base)
        assert abs(t-float(shown)) < 1e-3
        window = next(name for name,(lo,hi) in WINDOWS.items() if lo <= t <= hi)
        file = OUT/f'frame_{int(number)+1:03d}.jpg'
        frames.append(dict(file=file.name,sha256=sha(file),pts=int(pts),
            source_pts_seconds=t,window=window))
    # The coarse board reveals a dissolve near the end of the catalogue's
    # stationary-rev interval. Inspect every decoded frame around its end.
    detail_command = [FFMPEG, '-hide_banner', '-nostdin', '-y', '-to', '248.6',
        '-i', str(video), '-vf', "select='between(t,247.75,248.5)',showinfo",
        '-fps_mode', 'vfr', '-q:v', '2', str(OUT/'rev_edge_%03d.jpg')]
    done = subprocess.run(detail_command, check=True, capture_output=True)
    (OUT/'rev_edge_log.txt').write_bytes(done.stderr)
    rows = re.findall(r'\bn:\s*(\d+) pts:\s*(\d+) pts_time:([\d.]+)',
        done.stderr.decode('utf-8', errors='replace'))
    detail = []
    for number,pts,shown in rows:
        t = float(int(pts)*time_base)
        assert abs(t-float(shown)) < 1e-3
        file = OUT/f'rev_edge_{int(number)+1:03d}.jpg'
        detail.append(dict(file=file.name,sha256=sha(file),pts=int(pts),
            source_pts_seconds=t,window='rev_edit_detail'))
    frames += detail
    sheets = []
    for window in [*WINDOWS,'rev_edit_detail']:
        selected = [row for row in frames if row['window']==window]
        for start in range(0,len(selected),20):
            subset = selected[start:start+20]
            board = Image.new('RGB',(1280,((len(subset)+3)//4)*204),'#111a22')
            draw = ImageDraw.Draw(board)
            for i,row in enumerate(subset):
                x,y=i%4*320,i//4*204
                with Image.open(OUT/row['file']) as im:
                    board.paste(im.resize((320,180)),(x,y))
                draw.text((x+5,y+183),f"{row['file']} | {row['source_pts_seconds']:.6f} s",fill='white')
            file = OUT/f'{window}_{start//20+1}.jpg'
            board.save(file,quality=94)
            sheets.append(dict(file=file.name,sha256=sha(file),frames=[r['file'] for r in subset]))
    evidence = dict(schema='vsl.video-state-frames/1',script_sha256=sha(__file__),
        catalog_sha256=sha(CATALOG),video=source['video'],video_sha256=sha(video),
        stream=stream,command=command,windows=WINDOWS,frames=frames,sheets=sheets,
        detail_command=detail_command,detail_window=[247.75,248.5],
        processing='Video only, decoded from start; coarse windows every fifteenth source frame; stationary-rev edit detail every frame. No audio extraction or image enhancement.',
        limits=['Sampled frames constrain visible composition, not all intervening actions.',
            'Frame time is exact source PTS; independent audio/video offset is not measured.',
            'No RPM, pedal, gear, load, injector or acoustic transition telemetry is inferred.'])
    (OUT/'frames.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps(dict(frames=len(frames),sheets=sheets),indent=2))


if __name__=='__main__':
    main()
