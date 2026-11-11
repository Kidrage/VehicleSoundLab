"""Measure actual bank-source repetition and pressure-control invariants."""
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
OUT=ROOT/'renders/v0.9.0'


def main():
    metrics={};inputs={};fig,axes=plt.subplots(2,1,figsize=(11,7),constrained_layout=True)
    for name,rpm,ax in zip(['mid','high'],[4000,8000],axes):
        case={};lag=round(48000*120/rpm)
        for tag in ['bypass','varied']:
            banks=[];errors=[]
            for side in ['left','right']:
                file=OUT/f'stems/{name}_{tag}_exhaust_{side}.wav';inputs[str(file.relative_to(OUT)).replace('\\','/')]=sha(file)
                x,sr=sf.read(file);x=x[int(2*sr):int(3.8*sr)];banks.append(x)
                errors.append(float(10*np.log10(max(float(np.mean((x[lag:]-x[:-lag])**2)),1e-30)/np.mean(x[lag:]**2))))
            hz,power=signal.welch(banks[0],sr,nperseg=32768,noverlap=24576,scaling='density')
            # Zoom is for resolving sidebands; no spectral matching to a recording.
            ax.plot(hz,10*np.log10(np.maximum(power,1e-30)),label=tag,lw=.8)
            case[tag]=dict(cycle_lag_samples=lag,adjacent_720_cycle_difference_to_signal_db=errors,
                bank_rms_dbfs=[rms(x) for x in banks],bank_mean_power_dbfs=rms(np.column_stack(banks)))
        assert min(case['varied']['adjacent_720_cycle_difference_to_signal_db'])>max(case['bypass']['adjacent_720_cycle_difference_to_signal_db'])+30
        metrics[name]=case
        ax.set(title=f'{name}: actual left bank OSC, 2.0-3.8 s',xlabel='Hz',ylabel='PSD dBFS/Hz',xlim=(1000,3000),ylim=(-145,-25));ax.grid(alpha=.2);ax.legend()
    fig.savefig(OUT/'pressure_spectra.png',dpi=140);plt.close(fig)
    traces={}
    for name in ['idle','mid','high','lift','downshift']:
        file=OUT/f'{name}_varied.csv';inputs[file.name]=sha(file)
        with file.open() as f:traces[name]=list(csv.DictReader(f))
    lift=traces['lift'];cut=[r for r in lift if 3.8<float(r['seconds'])<4.7]
    assert len(cut)>5 and all(r['fuel_mode']=='CUT' for r in cut)
    for side in ['l','r']:assert len({r[f'pressure_events_{side}'] for r in cut})==1
    blips=[r for r in traces['downshift'] if float(r['blip'])>0];assert blips
    assert all(float(r['fuel_command'])==1 and float(r['throttle'])==0 for r in blips)
    assert int(blips[-1]['pressure_events_l'])>int(blips[0]['pressure_events_l'])
    controls={}
    for name,rows in traces.items():
        controls[name]={}
        for side in ['l','r']:
            arrival=np.array([float(r[f'arrival_offset_us_{side}']) for r in rows]);gain=np.array([float(r[f'pressure_gain_{side}']) for r in rows])
            assert abs(arrival).max()<=42.00001 and gain.min()>=1-.18*.35-1e-6 and gain.max()<=1+.18*.35+1e-6
            controls[name][side]=dict(max_arrival_offset_us=float(abs(arrival).max()),minimum_pressure_gain=float(gain.min()),maximum_pressure_gain=float(gain.max()))
        assert min(float(r['modulation_stretch']) for r in rows)>=1
    mid=traces['mid'];t=np.array([float(r['seconds']) for r in mid])
    fig,axes=plt.subplots(2,1,figsize=(11,6),constrained_layout=True)
    for side in ['l','r']:
        axes[0].plot(t,[float(r[f'pressure_gain_{side}']) for r in mid],label=side)
        axes[1].plot(t,[float(r[f'arrival_offset_us_{side}']) for r in mid],label=side)
    axes[0].set(title='4000 RPM: sparse control snapshots (not firing-time resolution)',ylabel='Pressure gain');axes[0].legend();axes[0].grid(alpha=.2)
    axes[1].set(xlabel='Scenario seconds',ylabel='Arrival offset us');axes[1].legend();axes[1].grid(alpha=.2)
    fig.savefig(OUT/'pressure_states.png',dpi=140);plt.close(fig)
    report=dict(result='pass',script_sha256=sha(Path(__file__)),inputs=inputs,steady_bank_sources=metrics,control_bounds=controls,
        cut_window=dict(source_seconds=[3.8,4.7],rows=len(cut),pressure_events_frozen=True),
        downshift=dict(blip_rows=len(blips),driver_pedal_closed=True,refuel_command=True,pressure_events_resume=True),
        plots={name:sha(OUT/name) for name in ['pressure_spectra.png','pressure_states.png']},
        limits='Known stationary synthesized 720-degree repeat error and sparse parameter snapshots only. Lower repetition is not perceptual accuracy; no recording-derived ignition timing or mode fit.')
    (OUT/'pressure_measurements.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(metrics,indent=2))


if __name__=='__main__':main()
