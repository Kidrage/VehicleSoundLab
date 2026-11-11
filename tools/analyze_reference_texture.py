"""Fixed-line screen on approved mixed recordings; never an engine modal fit."""
from pathlib import Path
import csv
import json
from runtime_review import ROOT,sha
import numpy as np
import soundfile as sf
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=ROOT/'references/analysis/mechanical_texture_v1'
CASES=[('A_tailpipe_idle','A',208,213),('A_bay_context','A',270,277),
       ('A_stationary_blips','A',237,249),('B_cabin_pull','B',218,230)]


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    fig,axes=plt.subplots(4,1,figsize=(12,11),constrained_layout=True)
    rows=[]
    for (name,identity,start,stop),ax in zip(CASES,axes):
        source=ROOT/f'references/clean/{identity}_decoded_float.wav'
        with sf.SoundFile(source) as file:
            sr=file.samplerate;file.seek(int(start*sr));x=file.read(int((stop-start)*sr),always_2d=True)
        hz,t,z=signal.stft(x,sr,nperseg=4096,noverlap=3856,axis=0,boundary=None,padded=False,scaling='psd')
        power=(abs(z)**2).mean(axis=1) # Mean channel powers, never sum binaural waveforms.
        db=10*np.log10(np.maximum(power,1e-30))
        ax.pcolormesh(t+start,hz,db,shading='auto',vmin=-85,vmax=-20,cmap='magma',rasterized=True)
        ax.set(title=name,ylabel='Hz',xlabel='Original recording seconds',ylim=(1000,8000))
        prominence=[];screen={}
        for centre in [1760,3100]:
            peak=power[abs(hz-centre)<=25].max(axis=0)
            local=power[(abs(hz-centre)>=100)&(abs(hz-centre)<=300)]
            ratio=10*np.log10(np.maximum(peak,1e-30)/np.maximum(np.median(local,axis=0),1e-30))
            prominence.append(ratio)
            screen[str(centre)]=dict(median_local_prominence_db=float(np.median(ratio)),
                p10_db=float(np.percentile(ratio,10)),p90_db=float(np.percentile(ratio,90)),
                fraction_of_frames_above_6db=float(np.mean(ratio>6)))
            ax.axhline(centre,color='cyan',alpha=.5,ls='--',lw=.7)
        path=OUT/f'{name}.csv'
        with path.open('w',newline='') as handle:
            w=csv.writer(handle);w.writerow(['source_seconds','1760_local_prominence_db','3100_local_prominence_db']);w.writerows(zip(t+start,*prominence))
        rows.append(dict(name=name,master=str(source.relative_to(ROOT)).replace('\\','/'),master_sha256=sha(source),
            source_seconds=[start,stop],channels=x.shape[1],fixed_line_screen=screen))
    fig.savefig(OUT/'recorded_texture.png',dpi=140);plt.close(fig)
    report=dict(schema='vsl.mixed-recording-texture/1',script_sha256=sha(Path(__file__)),recordings=rows,
        analysis=dict(window='4096-frame Hann',hop_frames=240,window_seconds=4096/48000,
            frequency_resolution_hz=48000/4096,channel_policy='Mean stereo power, no waveform folding',
            plot='Common absolute PSD scale -85..-20 dBFS/Hz; no independent normalization',
            screen='Peak within +/-25 Hz divided by median bins 100..300 Hz away; exploratory local contrast only'),
        decision='Replace self-sustained mechanical carriers with struck modes as a causal engineering extension; these mixed recordings do not identify the new mode frequencies, damping or valve timing.',
        limits=['Harmonics can cross either screen frequency; a local peak does not prove a structural mode.',
            'Microphone position, intake/exhaust, RPM, reflections and recording processing are confounded. No source separation or synchronized telemetry.',
            'No new cleaning, reference gain changes, mono folding, source-time fitting or runtime source playback.'])
    report['outputs']={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='results.json'}
    (OUT/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({r['name']:r['fixed_line_screen'] for r in rows},indent=2))


if __name__=='__main__':main()
