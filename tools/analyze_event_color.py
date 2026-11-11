"""Independent filter oracle and mechanism measurements, never a realism score."""
import json
from runtime_review import ROOT, sha
from cycle_prediction import band_prediction
import numpy as np
import soundfile as sf
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=ROOT/'renders/event_color_v1'


def main():
    if (OUT/'analysis.json').exists():raise SystemExit('Preserve completed event coloration analysis.')
    records=np.fromfile(OUT/'mid/full_taps.f64',dtype='<f8').reshape(-1,8)
    assert records.shape==(240000,8) and np.isfinite(records).all()
    # scipy designs a bilinear Butterworth independently of the C RBJ recipe.
    # Whole recorded DOUBLE input drives lfilter, not the C recurrence state.
    low=signal.lfilter(*signal.butter(2,1400,fs=48000),records[:,:2],axis=0)
    upper=signal.lfilter(*signal.butter(2,4500,fs=48000),records[:,:2],axis=0)
    mid_mod=records[:,[4,6]];high_mod=records[:,[5,7]]
    delta=.45*mid_mod*(upper-low)+.90*high_mod*(records[:,:2]-upper)
    expected=records[:,:2]+delta
    error=float(abs(expected-records[:,2:4]).max());assert error<1e-12,error
    source_error={}
    for c,side in enumerate(['left','right']):
        before,sr=sf.read(OUT/f'mid/fixed_source_exhaust_{side}.wav')
        after,ar=sf.read(OUT/f'mid/full_source_exhaust_{side}.wav')
        assert sr==ar==48000
        sample_error=float(abs(after-before-delta[:,c]).max())
        assert sample_error<1.3e-7,sample_error
        source_error[side]=sample_error
    runtime={}
    for name,rpm in [('low',1200),('mid',4000),('high',8000)]:
        runtime[name]={};times=np.arange(2.5,4.8,.005);frequency=np.full(len(times),rpm*10/240)
        for tag in ['fixed','half','full']:
            x,sr=sf.read(OUT/f'{name}/{tag}.wav',always_2d=True)
            rows=band_prediction(x,sr,times,frequency,divisors=(5,),bands=((1200,3000),(3000,8000)))
            assert all(r['status']=='measured' for r in rows)
            runtime[name][tag]=rows
        print(json.dumps(dict(case=name,error_3_8k_db={tag:runtime[name][tag][1]['error_to_signal_db_lr'] for tag in runtime[name]})),flush=True)
    result=dict(result='pass',experiment='event_color_v1',
        independent_Butterworth_double_oracle_max_error=error,
        independently_predicted_source_delta_max_float_error=source_error,
        tap_columns=['main_fired_left','main_fired_right','colored_main_left','colored_main_right',
                     'mod_left_mid','mod_left_high','mod_right_mid','mod_right_high'],
        runtime_conditional_waveform_prediction=runtime,
        definitions='Known model bank frequency=RPM*10/240; divisor5 is its full720-degree cycle. Past8-cycle mean predicts next4 in supplied coordinates, same causal analysis filters. A larger error is not more realistic or a noise percentage.',
        evidence_scope='Independent signal-flow check and effect size only. No fitted physical RPM/load or matched reference experiment.',
        inputs={p.relative_to(OUT).as_posix():sha(p) for p in [OUT/'mid/full_taps.f64',OUT/'results.json']})
    (OUT/'analysis.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    fig,axes=plt.subplots(3,1,figsize=(11,8),constrained_layout=True)
    interval=np.arange(144000,146400);t=(interval-interval[0])/48
    axes[0].plot(t,records[interval,0],label='Native main fired pressure',lw=1)
    axes[0].plot(t,records[interval,2],label='Full event coloration',lw=1,alpha=.85)
    axes[0].set(ylabel='Pre-scene sample',title='4000 engineering RPM: same firing events, changing main-pressure contour')
    axes[0].legend(loc='upper right')
    filtered=signal.sosfilt(signal.butter(4,[3000,8000],btype='bandpass',fs=48000,output='sos'),records[:,[0,2]],axis=0)
    axes[1].plot(t,filtered[interval,0],label='Native',lw=1)
    axes[1].plot(t,filtered[interval,1],label='Full',lw=1,alpha=.85)
    axes[1].set(ylabel='3-8 kHz analysis',xlabel='Time from 3.0 s (ms)')
    axes[2].plot(t,records[interval,4]*.45,label='Left mid gain change')
    axes[2].plot(t,records[interval,5]*.90,label='Left high gain change')
    axes[2].set(ylabel='Dimensionless',xlabel='Time from 3.0 s (ms)',title='Event controls: no new random stream or crank timing')
    axes[2].legend(loc='upper right')
    fig.savefig(OUT/'main_pressure_example.png',dpi=150);plt.close(fig)
    print(json.dumps(dict(double_oracle_error=error,source_delta_errors=source_error)),flush=True)


if __name__=='__main__':main()
