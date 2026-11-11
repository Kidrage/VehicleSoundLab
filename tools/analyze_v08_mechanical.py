"""Audit actual exported mechanical objects and controller histories."""
from pathlib import Path
import csv
import json
from runtime_review import ROOT,sha,rms
import numpy as np
import soundfile as sf
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=ROOT/'renders/v0.8.0'


def main():
    fig,axes=plt.subplots(3,1,figsize=(11,9),constrained_layout=True)
    metrics={};inputs={}
    for name,ax in zip(['idle','mid','high'],axes):
        case={}
        for tag in ['legacy','driven']:
            file=OUT/f'stems/{name}_{tag}_mechanical.wav';inputs[str(file.relative_to(OUT)).replace('\\','/')]=sha(file)
            x,sr=sf.read(file);x=x[int(2*sr):int(3.8*sr)]
            hz,power=signal.welch(x,sr,nperseg=16384,noverlap=8192,scaling='density')
            ax.plot(hz,10*np.log10(np.maximum(power,1e-30)),label=tag,lw=.85)
            den=power[(hz>=1200)&(hz<=8000)].sum()
            lines={str(f):float(power[abs(hz-f)<=15].sum()/max(den,1e-30)) for f in [1760,3100]}
            banks=[sf.read(OUT/f'stems/{name}_{tag}_exhaust_{side}.wav')[0][int(2*sr):int(3.8*sr)] for side in ['left','right']]
            bank_power=sum(float(np.mean(y*y)) for y in banks)/2
            case[tag]=dict(mechanical_rms_dbfs=rms(x),mechanical_vs_mean_bank_power_db=float(10*np.log10(np.mean(x*x)/max(bank_power,1e-30))),
                fixed_band_fractions_of_1200_8000_power=lines,peak=float(abs(x).max()))
        metrics[name]=case
        ax.set(title=f'{name}: actual pre-spatial mechanical object, 2.0-3.8 s',xlim=(400,8000),ylim=(-145,-45),xlabel='Hz',ylabel='PSD dBFS/Hz');ax.legend();ax.grid(alpha=.2)
    fig.savefig(OUT/'mechanical_spectra.png',dpi=140);plt.close(fig)
    with (OUT/'lift_driven.csv').open() as f:lift=list(csv.DictReader(f))
    with (OUT/'shifts_driven.csv').open() as f:shift=list(csv.DictReader(f))
    with (OUT/'downshift_driven.csv').open() as f:down=list(csv.DictReader(f))
    def value(rows,key):return np.array([float(r[key]) for r in rows])
    cut=[r for r in lift if 3.8<float(r['seconds'])<4.7]
    assert len(cut)>5 and all(r['fuel_mode']=='CUT' and float(r['firing_excitation'])<1e-10 for r in cut)
    assert len({r['fired_strikes'] for r in cut})==1
    assert int(cut[-1]['rotating_strikes'])>int(cut[0]['rotating_strikes'])
    lift_mech,sr=sf.read(OUT/'stems/lift_driven_mechanical.wav');assert rms(lift_mech[int(3.8*sr):int(4.5*sr)])> -90
    blip=[r for r in down if float(r['blip'])>0];assert blip
    assert all(float(r['fuel_command'])==1 and float(r['throttle'])==0 for r in blip)
    assert int(blip[-1]['fired_strikes'])>int(blip[0]['fired_strikes'])
    off=[r for r in shift if r['lifecycle']=='OFF'];assert off
    energy=value(off,'mechanical_stored_energy')
    assert energy[0]>0 and np.all(np.diff(energy)<=0) and energy[-1]==0
    assert len({r['rotating_strikes'] for r in off})==1 and len({r['fired_strikes'] for r in off})==1
    fig,axes=plt.subplots(2,1,figsize=(11,6),constrained_layout=True)
    axes[0].plot(value(lift,'seconds'),value(lift,'firing_excitation'),label='Fired pressure')
    axes[0].plot(value(lift,'seconds'),value(lift,'mechanical_motion_gain')*10,label='Rotating mechanical envelope x10')
    axes[0].set(title='Fixed-RPM lift: motion continues during fuel cut',ylabel='Control gain');axes[0].legend();axes[0].grid(alpha=.2)
    for key in ['rotating_strikes','fired_strikes']:axes[1].plot(value(lift,'seconds'),value(lift,key),label=key)
    axes[1].set(xlabel='Scenario seconds',ylabel='Cumulative applied strikes');axes[1].legend();axes[1].grid(alpha=.2)
    fig.savefig(OUT/'mechanical_states.png',dpi=140);plt.close(fig)
    for name in ['lift_driven.csv','shifts_driven.csv','downshift_driven.csv','stems/lift_driven_mechanical.wav']:inputs[name]=sha(OUT/name)
    report=dict(result='pass',script_sha256=sha(Path(__file__)),inputs=inputs,steady_sources=metrics,
        cut_window=dict(source_seconds=[3.8,4.7],rows=len(cut),fired_strikes_constant=True,rotational_strikes_continue=True,
            mechanical_rms_dbfs=rms(lift_mech[int(3.8*sr):int(4.5*sr)])),
        downshift=dict(blip_rows=len(blip),closed_driver_pedal=True,refuel_command=True,fired_strikes_resume=True),
        shutdown=dict(off_rows=len(off),no_new_strikes=True,first_off_energy=float(energy[0]),
            stored_energy_decays_monotonically_to_zero=True,final_off_energy=float(energy[-1])),
        plots={n:sha(OUT/n) for n in ['mechanical_spectra.png','mechanical_states.png']},
        limits='Actual source mechanism and signal measurements only. Modes/valve timing uncalibrated; no perceptual realism percentage or claim of a measured block transfer function.')
    (OUT/'mechanical_measurements.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report['steady_sources'],indent=2))


if __name__=='__main__':main()
