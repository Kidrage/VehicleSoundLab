"""Measure actual fuel-aware exports, including dry per-source ablations."""
from pathlib import Path
import csv
import hashlib
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/python_deps'))
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=ROOT/'renders/v0.7.0'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def rows(name):
    with (OUT/name).open() as file:return list(csv.DictReader(file))


def main():
    measurements={};windows={'before':[2.5,2.9],'cut':[3.8,4.5],'recovered':[5.4,6.2]}
    stem_inputs={}
    for tag in ['bypass','enabled','no_pump']:
        measurements[tag]={}
        for path in sorted((OUT/'stems').glob(f'dry_lift_{tag}_*.wav')):
            name=path.stem.removeprefix('dry_lift_'+tag+'_');x,sr=sf.read(path);info=sf.info(path)
            assert sr==48000 and info.channels==1 and info.subtype=='FLOAT' and info.frames==360000
            stem_inputs[str(path.relative_to(OUT)).replace('\\','/')]=sha(path)
            measurements[tag][name]={key:float(10*np.log10(max(float(np.mean(x[int(lo*sr):int(hi*sr)]**2)),1e-30))) for key,(lo,hi) in windows.items()}
    assert len(measurements['enabled'])==10
    delta=measurements['enabled']['exhaust_left']['cut']-measurements['bypass']['exhaust_left']['cut']
    assert delta< -10 and measurements['enabled']['exhaust_left']['cut']> -90
    assert measurements['no_pump']['exhaust_left']['cut']< -160
    independent=[]
    for name in ['body','mechanical','intake','air_left','air_right','events','road','wind']:
        a=OUT/f'stems/dry_lift_bypass_{name}.wav';b=OUT/f'stems/dry_lift_enabled_{name}.wav'
        assert a.read_bytes()==b.read_bytes(),name
        independent.append(name)
    down=rows('downshift_enabled.csv');blips=[r for r in down if float(r['blip'])>0]
    assert blips and all(float(r['fuel_command'])==1 and float(r['throttle'])<.001 for r in blips)
    coast=[r for r in down if float(r['seconds'])>=10.5]
    assert all(float(b['speed_kph'])<=float(a['speed_kph'])+.001 for a,b in zip(coast,coast[1:]))
    assert len({r['hits'] for r in coast})==1
    assert any(r['fuel_mode']=='CUT' and float(r['firing_excitation'])<1e-6 for r in coast)
    trace=rows('dry_lift_enabled.csv')
    fig,axes=plt.subplots(2,1,figsize=(11,6.4),constrained_layout=True)
    times=[float(r['seconds']) for r in trace]
    axes[0].plot(times,[float(r['firing_excitation']) for r in trace],label='Fired pressure gate')
    axes[0].plot(times,[float(r['pumping_excitation']) for r in trace],label='Motored pressure drive')
    axes[0].plot(times,[float(r['load']) for r in trace],ls=':',label='Signed bench load')
    axes[0].set(title='5000 RPM bench: same crank speed, different excitation',ylabel='Control / excitation')
    for tag in ['bypass','enabled','no_pump']:
        x,sr=sf.read(OUT/f'stems/dry_lift_{tag}_exhaust_left.wav');n=len(x)//2400
        db=10*np.log10(np.maximum(np.mean(x[:n*2400].reshape(n,2400)**2,axis=1),1e-16))
        axes[1].plot((np.arange(n)+.5)*.05,db,label=tag)
    axes[1].set(xlabel='Rendered file seconds',ylabel='Left exhaust stem RMS dBFS',ylim=(-100,-10))
    for axis in axes:
        axis.grid(alpha=.2);axis.legend(fontsize=8);axis.axvspan(3,4.8,color='grey',alpha=.12)
    fig.savefig(OUT/'dry_lift_sources.png',dpi=140);plt.close(fig)
    t=np.array([float(r['seconds']) for r in down])
    fig,axes=plt.subplots(3,1,figsize=(11,7.2),constrained_layout=True)
    axes[0].plot(t,[float(r['rpm']) for r in down],label='RPM')
    axes[0].plot(t,[float(r['shift_target_rpm']) if r['shift_stage']!='NONE' else np.nan for r in down],ls=':',label='Match target')
    axes[0].set(ylabel='RPM',title='Closed-pedal braking: cut, internal blip, match and re-engagement')
    axes[1].plot(t,[float(r['throttle']) for r in down],label='Driver pedal')
    axes[1].plot(t,[float(r['blip']) for r in down],label='Internal blip')
    axes[1].plot(t,[float(r['firing_excitation']) for r in down],label='Actual fired gate')
    axes[1].set(ylabel='0 to 1')
    axes[2].plot(t,[float(r['speed_kph']) for r in down],label='Speed kph')
    axes[2].plot(t,[float(r['gear'])*10 for r in down],label='Gear x 10')
    axes[2].set(xlabel='Rendered file seconds',ylabel='Speed / gear')
    for axis in axes:axis.grid(alpha=.2);axis.legend(fontsize=8,ncol=3);axis.set_xlim(9,18)
    fig.savefig(OUT/'downshift_fueling.png',dpi=140);plt.close(fig)
    report=dict(version='0.7.0',result='pass',script_sha256=sha(Path(__file__)),
        window_file_seconds=windows,stem_rms_dbfs=measurements,
        motored_vs_fired_exhaust_cut_window_db=delta,
        dry_non_exhaust_stems_bit_identical=independent,
        downshift=dict(blip_trace_rows=len(blips),blips_refuel=True,closed_driver_pedal=True,
            speed_monotonic_under_braking=True,no_new_internal_blip_hits=True),
        inputs=stem_inputs,
        plots={name:sha(OUT/name) for name in ['dry_lift_sources.png','downshift_fueling.png']},
        limits=['Actual rendered mechanism/energy verification, not subjective realism.',
                'Dry diagnostic disables IR to isolate source envelopes; normal body stem includes an exhaust-driven IR return.',
                'Motored cavity settings and all ECU thresholds are engineering assumptions.'])
    (OUT/'excitation_measurements.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['result','motored_vs_fired_exhaust_cut_window_db','dry_non_exhaust_stems_bit_identical','downshift']},indent=2))


if __name__=='__main__':main()
