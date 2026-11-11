"""Exploratory decay observations; never infer ECU fuel cut from a sound drop."""
from pathlib import Path
import csv
import hashlib
import json
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/python_deps'))
import numpy as np
import soundfile as sf
from PIL import Image,ImageDraw,ImageFont
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=ROOT/'references/analysis/overrun_v1'
BANDS=[(28,120),(120,400),(400,1200),(1200,3000),(3000,8000),(8000,16000)]
CASES=[('A_stationary','A',237,249),('A_moving','A',316,319.5),('B_cabin','B',218,230)]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def observation(name,identity,start,stop,axes):
    path=ROOT/f'references/clean/{identity}_decoded_float.wav'
    with sf.SoundFile(path) as file:
        file.seek(int(start*file.samplerate));x=file.read(int((stop-start)*file.samplerate),always_2d=True);sr=file.samplerate
    hz,t,z=signal.stft(x,sr,nperseg=4096,noverlap=3856,axis=0,boundary=None,padded=False,scaling='psd')
    # scipy returns frequency, channel, time. Never sum binaural waveforms.
    power=(abs(z)**2).mean(axis=1)
    powers=np.array([power[(hz>=lo)&(hz<hi)].sum(axis=0)*2*sr/4096 for lo,hi in BANDS])
    db=10*np.log10(np.maximum(powers,1e-30));times=t+start
    mid=powers[2:5].sum(axis=0)
    # Most negative fixed-250ms change is an energy-drop candidate, not a
    # confirmed gear, pedal, combustion or fuel-cut transition.
    lag=50
    change=10*np.log10(np.maximum(mid[lag:],1e-30)/np.maximum(mid[:-lag],1e-30))
    at=int(np.argmin(change));before=times[at];after=times[at+lag]
    axes.set_title(f'{name}: recorded bands; largest 250 ms drop marked')
    for y,(lo,hi) in zip(db,BANDS):axes.plot(times,y,label=f'{lo}-{hi} Hz',lw=1)
    axes.axvspan(before,after,color='grey',alpha=.14)
    axes.set(ylabel='Band power dBFS',xlabel='Original source seconds',ylim=(-85,3));axes.grid(alpha=.2)
    file=OUT/f'{name}.csv'
    with file.open('w',newline='') as handle:
        writer=csv.writer(handle);writer.writerow(['source_seconds',*[f'{a}_{b}_dbfs' for a,b in BANDS]])
        writer.writerows(zip(times,*db))
    return dict(source=identity,source_seconds=[start,stop],master=str(path.relative_to(ROOT)).replace('\\','/'),
        master_sha256=sha(path),channels=x.shape[1],samples=len(x),
        energy_drop_candidate=dict(before_source_seconds=float(before),after_source_seconds=float(after),
            mid_high_change_db=float(change[at]),individual_band_change_db=(db[:,at+lag]-db[:,at]).tolist()),
        limits='Exploratory same-recording energy drop only. No known pedal/gear/RPM/fuel state, source separation or physical time constants.')


def upstream():
    # Inspect the actual pinned codebox and controller, preserving exact evidence.
    manifest=json.loads((ROOT/'research/upstream_snapshot.json').read_text())
    path=ROOT/'research/upstream/gen/v10_powertrain.gendsp'
    item=next(x for x in manifest['files'] if x['path']=='gen/v10_powertrain.gendsp')
    assert sha(path)==item['sha256']
    data=json.loads(path.read_text())
    def codes(node):
        result=[]
        if isinstance(node,dict):
            if node.get('maxclass')=='codebox':result.append(node.get('code',''))
            for value in node.values():result+=codes(value)
        elif isinstance(node,list):
            for value in node:result+=codes(value)
        return result
    code='\n'.join(codes(data));assert 'combustion_gain' in code
    lines=[line for line in code.splitlines() if any(s in line for s in ['run =','bank_l =','residual_l =','phase_r ='])]
    controller=ROOT/'research/upstream_v6/code/drive_model.js'
    control_manifest=json.loads((ROOT/'research/v6_control_snapshot.json').read_text())
    item=next(x for x in control_manifest['files'] if x['path']=='code/drive_model.js')
    assert sha(controller)==item['sha256']
    text=controller.read_text(encoding='utf-8')
    return dict(revision=manifest['revision'],gen_sha256=sha(path),exact_gen_lines=lines,
        drive_controller_sha256=sha(controller),
        controller_has_fuel_cut_identifier='fuel_cut' in text or 'fuelCut' in text,
        relationship='V6 separates running/combustion/shift controls, but its inspected V10 multiplies them into one run gate. This iteration adds independent motored-vs-fired pressure, rather than claiming an existing V6 ECU model was ported.')


def video_context():
    video=ROOT/'references/raw/A_context_360p.mp4'
    times=[237.7,238.1,238.4,318.6,318.85,319.1]
    board=Image.new('RGB',(1200,500),(20,25,34));draw=ImageDraw.Draw(board)
    font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',17)
    for i,seconds in enumerate(times):
        path=OUT/f'A_frame_{seconds}.jpg'
        subprocess.run(['D:/repo/tools/ffmpeg/bin/ffmpeg.exe','-v','error','-nostdin','-y','-ss',str(seconds),'-i',str(video),'-frames:v','1',str(path)],check=True)
        with Image.open(path) as image:
            image.thumbnail((394,220));x=i%3*400;y=i//3*250;board.paste(image,(x,y))
            draw.text((x+7,y+225),f'A requested source {seconds} s',font=font,fill='white')
    board.save(OUT/'video_context.jpg')
    return dict(video=str(video.relative_to(ROOT)).replace('\\','/'),sha256=sha(video),requested_source_seconds=times,
        scope='Sparse visual context only. Does not establish pedal, RPM, gear, injector state or absence of intervening cuts. B has no inspected video.')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    fig,axes=plt.subplots(3,1,figsize=(12,10),constrained_layout=True)
    rows=[observation(*case,axis) for case,axis in zip(CASES,axes)]
    axes[0].legend(ncol=3,fontsize=8)
    fig.savefig(OUT/'recording_decays.png',dpi=140);plt.close(fig)
    report=dict(schema='vsl.overrun-observations/1',script_sha256=sha(Path(__file__)),
        analysis=dict(window_frames=4096,hop_frames=240,sample_rate=48000,
            window_seconds=4096/48000,comparison_seconds=.25,channel_policy='Mean of channel powers, no waveform folding',
            timing_limit='85.33 ms support; 5 ms hop is not event accuracy. Drops can include pitch, perspective, edits and recording processing.'),
        bands_hz=BANDS,recordings=rows,upstream=upstream(),video_context=video_context(),
        model_decision='Do not fit ECU thresholds/dwell to these energy drops. Separate sound mechanisms using explicit engineering controls, leaving calibration open.')
    report['outputs']={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='results.json'}
    (OUT/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({r['source']+str(r['source_seconds']):r['energy_drop_candidate'] for r in rows},indent=2))


if __name__=='__main__':main()
