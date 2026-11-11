"""Reproducible frame PTS and raw stereo startup observations; no RPM fitting."""
import csv
import json
import re
import subprocess
from pathlib import Path
from fractions import Fraction
from runtime_review import ROOT, sha
from reference_segments import checked_source, read_segment
import numpy as np
from scipy import signal
from PIL import Image, ImageDraw
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = ROOT / 'references/analysis/lifecycle_v1'
FFMPEG = Path('D:/repo/tools/ffmpeg/bin/ffmpeg.exe')
FFPROBE = FFMPEG.with_name('ffprobe.exe')


def frames():
    source = checked_source('A'); video = ROOT/source['video']
    assert sha(video) == source['video_sha256']
    probe = json.loads(subprocess.check_output([str(FFPROBE), '-v', 'error',
        '-select_streams', 'v:0', '-show_entries',
        'stream=time_base,r_frame_rate,start_time,duration,width,height', '-of', 'json', str(video)]))['streams'][0]
    command = [str(FFMPEG), '-hide_banner', '-nostdin', '-y', '-to', '40.2',
        '-i', str(video), '-vf', "select='between(t,34.3,40.1)*not(mod(n,6))',showinfo",
        '-fps_mode', 'vfr', str(OUT/'lifecycle_%03d.jpg')]
    result = subprocess.run(command, check=True, capture_output=True)
    (OUT/'lifecycle_frame_log.txt').write_bytes(result.stderr)
    entries = re.findall(r'\bn:\s*(\d+) pts:\s*(\d+) pts_time:([\d.]+)', result.stderr.decode('utf-8', errors='replace'))
    time_base = Fraction(probe['time_base']); ledger = []
    for index, pts, shown in entries:
        file = OUT/f'lifecycle_{int(index)+1:03d}.jpg'
        exact_time = float(int(pts)*time_base)
        assert abs(exact_time-float(shown)) < 1e-5
        ledger.append(dict(file=file.name, sha256=sha(file), pts=int(pts), source_pts_seconds=exact_time))
    assert len(ledger) == len(list(OUT.glob('lifecycle_*.jpg')))
    board = Image.new('RGB', (4*320, ((len(ledger)+3)//4)*204), '#111a22')
    draw = ImageDraw.Draw(board)
    for i, row in enumerate(ledger):
        x,y=(i%4)*320,(i//4)*204
        with Image.open(OUT/row['file']) as im:board.paste(im.resize((320,180)),(x,y))
        draw.text((x+8,y+183), f"source PTS {row['source_pts_seconds']:.6f} s", fill='white')
    board.save(OUT/'lifecycle_contact.jpg', quality=92)
    return dict(video=source['video'], video_sha256=sha(video), stream=probe, command=command,
        extraction='Decoded from source start; no input seeking. Integer frame PTS times stream time_base.',
        alignment_limit=source['alignment'], frames=ledger)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    visual = frames()
    x, rate, provenance = read_segment('A_start_context', 'audio_onset_observation')
    first = provenance['source_seconds'][0]
    hz,t,z=signal.stft(x,rate,nperseg=2048,noverlap=1808,axis=0,boundary=None,padded=False,scaling='psd')
    power=abs(z)**2
    bands=[(30,150),(150,600),(600,3000),(3000,12000)]
    fig,axes=plt.subplots(3,1,figsize=(12,10),constrained_layout=True)
    tt=np.arange(len(x))/rate+first
    axes[0].plot(tt,x[:,0],lw=.25,label='L',alpha=.7)
    axes[0].plot(tt,x[:,1],lw=.25,label='R',alpha=.5)
    axes[0].set(title='A startup context: unchanged decoded stereo samples',ylabel='Amplitude')
    axes[0].legend(loc='upper left')
    mask=(hz>=30)&(hz<=4000)
    display=10*np.log10(np.maximum(power.mean(axis=1),1e-20))
    axes[1].pcolormesh(t+first,hz[mask],display[mask],shading='auto',vmin=-85,vmax=-20,cmap='magma')
    axes[1].set(yscale='log',ylim=(30,4000),ylabel='Hz',title='Mean L/R power for display only; 42.67 ms Hann, 5 ms hop')
    columns=[]
    for lo,hi in bands:
        # One-sided STFT PSD needs doubling except DC/Nyquist; neither is included.
        level=10*np.log10(np.maximum(2*(rate/2048)*power[(hz>=lo)&(hz<hi)].sum(axis=0),1e-20))
        columns.extend(level)
        axes[2].plot(t+first,level[0],lw=.8,label=f'{lo}-{hi} L')
        axes[2].plot(t+first,level[1],lw=.7,ls='--',label=f'{lo}-{hi} R')
    axes[2].legend(ncol=4,fontsize=8);axes[2].set(ylabel='Band power dBFS',xlabel='Decoded audio source seconds')
    for ax in axes:ax.grid(alpha=.15);ax.set_xlim(33,40)
    fig.savefig(OUT/'startup_observations.png',dpi=140);plt.close(fig)
    with (OUT/'startup_bands.csv').open('w',newline='') as file:
        writer=csv.writer(file);writer.writerow(['audio_source_seconds',*[f'{lo}_{hi}_{side}_dbfs' for lo,hi in bands for side in ['L','R']]])
        writer.writerows(zip(t+first,*columns))
    # Uniform half-second observations retain channel powers; no automatic catch label.
    windows=[]
    for start in np.arange(33,40,.5):
        block=x[round((start-first)*rate):round((start+.5-first)*rate)]
        windows.append(dict(audio_seconds=[float(start),float(start+.5)],
            rms_dbfs_lr=(10*np.log10(np.maximum(np.mean(block**2,axis=0),1e-20))).tolist()))
    result=dict(schema='vsl.lifecycle-observations/1',script_sha256=sha(Path(__file__)),
        audio=provenance,video=visual,half_second_observations=windows,
        limits=['Cluster boot and overlay fade are not proof of crank/catch timing.',
            'Audio includes control/handling sounds and mixed cabin acoustics; no source separation or RPM telemetry.',
            'STFT support 42.67 ms; hop is not time resolution. No data is fitted into runtime controls.'])
    (OUT/'observations.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(frames=len(visual['frames']),audio=provenance,windows=windows),indent=2))


if __name__=='__main__':main()
