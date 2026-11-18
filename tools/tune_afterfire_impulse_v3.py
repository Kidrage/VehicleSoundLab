"""Native-C pressure-pulse candidates, reference context and reproducible metrics."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy import signal
from vehicle_controller.native import Bridge, Engine
from vehicle_controller.afterfire import defaults


def metrics(x, rate=48000):
    x=np.asarray(x).mean(axis=1)
    energy=float(np.sum(x*x))
    cumulative=np.cumsum(x*x)/max(energy,1e-30)
    bands={}
    for lo,hi in ((40,250),(250,1200),(1200,3000),(3000,10000)):
        y=signal.sosfilt(signal.butter(3,[lo,hi],fs=rate,btype='bandpass',output='sos'),x)
        bands[f'{lo}-{hi}']=float(np.sum(y*y))
    total=sum(bands.values())
    return dict(peak=float(max(abs(x))),rms=float(np.sqrt(np.mean(x*x))),
        crest_db=float(20*np.log10(max(max(abs(x)),1e-15)/max(np.sqrt(np.mean(x*x)),1e-15))),
        energy_time_ms={str(q):float(np.searchsorted(cumulative,q)/rate*1000) for q in (.1,.5,.9)},
        first_5ms_energy_fraction=float(np.sum(x[:240]**2)/max(energy,1e-30)),
        band_energy_fraction={k:v/total for k,v in bands.items()})


def render_events(bridge,profile,control,policy,count=8):
    """Same manual scheduling/seeds, eight separated one-shots, exact C output."""
    c=deepcopy(control);c.update(ignition=0,start_id=0,backfire=0)
    p=deepcopy(policy);p.update(afterfire_min_count=1,afterfire_max_count=1)
    result=[]
    with Engine(bridge,0,{'afterfire':profile},event_policy=p) as e:
        e.set(c)
        # Let the existing monitor/event gain followers settle before comparing
        # attacks. An onset at sample zero would measure the host fade-in too.
        for _ in range(100):e.process(480)
        for k in range(count):
            c['events'].update(manual_type=3,manual_sequence=k+1);e.set(c)
            result.append(np.frombuffer(e.process(480),dtype='<f4').copy().reshape(-1,2))
            for _ in range(39):result.append(np.frombuffer(e.process(480),dtype='<f4').copy().reshape(-1,2))
    return np.concatenate(result)


def candidate(base,variant):
    doc=deepcopy(base);p=doc['parameters']
    doc['name']='G 风格回火 V3 · 压力爆破'+(' · 加厚' if variant=='heavy' else '')
    p.update(duration_seconds=.100,attack_seconds=.00022,release_seconds=.010,level=1.3)
    # Coherent leading pressure lobe, followed by a short damped rebound.
    # These are design parameters, not identified pipe modes or a shock solver.
    p['modes']=[dict(hz=hz,end_hz=hz,amplitude=amp,phase=np.pi/2,decay_seconds=decay)
        for hz,amp,decay in ((175,.55,.0075),(410,.85,.0032),(975,.34,.002))]
    p['bands']=[dict(hz=hz,q=q,amplitude=amp,attack_seconds=attack,decay_seconds=decay)
        for hz,q,amp,attack,decay in ((650,.35,2.4,.00025,.006),(2200,.45,.70,.0001,.0028))]
    if variant=='heavy':
        p['modes'][0].update(hz=112,end_hz=112,amplitude=1.0,decay_seconds=.014)
        p['bands'][0].update(hz=330,amplitude=1.8,decay_seconds=.012)
        p['bands'][1]['amplitude']=.60
    doc['design_note']='Reference-guided pressure-pulse candidate; three phase-aligned, strongly damped OSC plus two broad noise bands. Reduced high-band excitation; no new voice, DSP kernel, filter, room or PCM. Frequencies/decays remain sound-design parameters, not identified physical modes. Listening pending.'
    doc['supersedes_feedback']='V2 sounds too crisp, insufficient impulsive pressure/explosive body; user 2026-11-18.'
    return doc


def reference_regions(path,output):
    # Image review supports exhaust-event regions, not sample-exact physical labels.
    regions=[(153.0,153.5),(155.4,156.2),(156.9,157.8),(444.0,444.6),(446.8,449.6)]
    rows=[]
    with sf.SoundFile(path) as f:
        for i,(lo,hi) in enumerate(regions):
            f.seek(round(lo*f.samplerate));x=f.read(round((hi-lo)*f.samplerate),dtype='float32',always_2d=True)
            y=signal.sosfilt(signal.butter(2,[100,5000],fs=f.samplerate,btype='bandpass',output='sos'),x.mean(axis=1))
            energy=np.convolve(y*y,np.ones(96)/96,mode='same')
            before=np.convolve(energy,np.ones(960)/960,mode='full')[:len(energy)]
            score=energy/(before+max(float(np.mean(energy))*.05,1e-12))
            score[:1200]=0;score[-2400:]=0
            at=int(np.argmax(score));first=max(0,at-24)
            crop=x[first:first+2400]
            sf.write(output/f'Reference-context-{i+1}.wav',x,f.samplerate,subtype='FLOAT')
            rows.append(dict(context_seconds=[lo,hi],acoustic_candidate_seconds=lo+at/f.samplerate,
                contrast_score=float(score[at]),metrics_mixed_context=metrics(crop),
                physically_isolated=False,precise_flame_onset_alignment=False))
    return rows


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reference',type=Path,required=True);a=parser.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];b=Bridge(repo)
    base=json.loads((repo/'presets/events/reference_afterfire_G_v2.json').read_text(encoding='utf-8'))
    c,f=b.initial(0);c,_,p=defaults(b,0,c,f)
    profiles={'Previous-V2':base,'Pressure-V3':candidate(base,'pressure'),'Heavy-V3':candidate(base,'heavy')}
    results={};audio={}
    for name,doc in profiles.items():
        y=render_events(b,doc,c,p);audio[name]=y
        sf.write(a.output/(name+'.wav'),y,48000,subtype='FLOAT')
        (a.output/(name+'.json')).write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        results[name]=dict(full=metrics(y),first_event=metrics(y[:4800]),
            all_event_peaks=[float(np.max(abs(y[k*19200:(k+1)*19200]))) for k in range(8)])
    reference=reference_regions(a.reference,a.output)
    # Comparison uses the same gain; also provide explicit RMS-matched audit files.
    target=results['Previous-V2']['full']['rms']
    for name in ('Pressure-V3','Heavy-V3'):
        gain=target/results[name]['full']['rms']
        sf.write(a.output/(name+'-RMS-matched.wav'),audio[name]*gain,48000,subtype='FLOAT')
        results[name]['rms_match_gain_for_audit']=gain
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    fig,axes=plt.subplots(3,2,figsize=(12,8),layout='constrained')
    for row,(name,y) in enumerate(audio.items()):
        x=y[:4800].mean(axis=1);t=np.arange(len(x))/48
        axes[row,0].plot(t,x,linewidth=.7);axes[row,0].set(xlim=(0,45),ylim=(-.5,.5),title=name+' pressure waveform',xlabel='ms')
        freq,power=signal.welch(x,48000,nperseg=1024)
        axes[row,1].semilogx(freq,10*np.log10(power+1e-15));axes[row,1].set(xlim=(40,16000),ylim=(-120,-30),title='Spectrum, same output gain',xlabel='Hz')
    fig.savefig(a.output/'pulse-and-spectrum.png',dpi=140);plt.close(fig)
    report=dict(schema='vsl.afterfire-impulse-v3-tuning/1',library_sha256=b.sha256,
        candidates=results,reference=reference,runtime_kernel_unchanged=True,modes_per_voice=3,bands_per_voice=2,
        voice_capacity=4,no_new_contours_or_color_filters=True,
        limitations='Candidate frequencies and gains are engineered. Mixed reference windows do not isolate afterfire, compensate propagation, or identify physical pressure. Numerical metrics do not establish naturalness.')
    (a.output/'analysis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(results,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
