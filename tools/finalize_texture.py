"""Independent analytic controls, track-error sensitivity and readable figures."""
import csv
import json
from runtime_review import ROOT,sha
from pitch_warp import compensate
from texture_metrics import measure,TextureSettings
import numpy as np
from scipy.fft import next_fast_len
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=ROOT/'references/analysis/texture_v1'


def analytic_controls():
    rate=48000;t=np.arange(2*rate)/rate
    # Independent Parseval/power calibration: stereo anti-phase must not cancel.
    a=.2*np.cos(2*np.pi*4207*t+.3);stereo=np.column_stack((a,-a))
    power_checks={}
    for n in [1024,4096]:
        m,_=measure(stereo,rate,TextureSettings(window=n))
        b=m['bands'][1]['channels'];expected=10*np.log10(.2**2/2)
        observed=[b[ch]['power_dbfs']['median'] for ch in ['L','R']]
        assert max(abs(v-expected) for v in observed)<.002
        assert b['L']['power_dbfs']==b['R']['power_dbfs'] and np.max(abs(stereo.mean(axis=1)))==0
        power_checks[str(n)]=dict(expected_dbfs=float(expected),observed_dbfs=observed)
    # A different analytic pitch law with three known emitted multiples.
    t=np.arange(round(1.4*rate))/rate;k=-.85
    f=315*np.exp(k*t);phase=2*np.pi*315/k*(np.exp(k*t)-1)
    x=np.column_stack([sum(.07/n*np.cos(n*phase+.21*n+.2*c) for n in [7,13,31]) for c in range(2)])
    ii=np.arange(round(.1*rate),round(1.3*rate),48)
    y,meta,_=compensate(x,rate,t[ii],f[ii]);mid=y[round(.05*rate):-round(.05*rate)]
    freq=np.fft.rfftfreq(len(mid),1/rate);s=abs(np.fft.rfft(mid[:,0]*signal.windows.hann(len(mid),sym=False)))**2
    peaks=[]
    for n in [7,13,31]:
        expected=n*meta['reference_hz'];mask=abs(freq-expected)<5;ids=np.flatnonzero(mask)
        measured=float(freq[ids[np.argmax(s[mask])]])
        assert abs(measured-expected)<1
        peaks.append(dict(emitted_multiple=n,expected_hz=expected,peak_hz=measured))
    # Known pure OSC mixture with deliberately imperfect supplied frequency.
    # Shows what common bias/jitter can leave after compensation.
    t=np.arange(4*rate)/rate;f=120+80*np.sin(2*np.pi*1.5*t)
    phase=2*np.pi*120*t+80/1.5*(1-np.cos(2*np.pi*1.5*t));x=np.zeros((len(t),2))
    for n in range(1,101):
        amp=.008*np.exp(-((n*f-5000)/2500)**2)
        for c in range(2):x[:,c]+=amp*np.cos(n*phase+.17*n+.11*c*n)
    ii=np.arange(round(.1*rate),round(3.9*rate),48);sensitivity=[]
    for amplitude in [0,.25,.5,1.]:
        supplied=f[ii]+amplitude*np.sin(2*np.pi*5*t[ii])
        y,meta,_=compensate(x,rate,t[ii],supplied)
        n=next_fast_len(round(12*rate/meta['reference_hz']))
        m,_=measure(y,rate,TextureSettings(window=n,hop=round(n/16),envelope_sigma_hz=3*meta['reference_hz']),
            bands=[(20*meta['reference_hz'],40*meta['reference_hz'])])
        sensitivity.append(dict(supplied_pitch_error_amplitude_hz=amplitude,pitch_error_rate_hz=5,
            reference_hz=meta['reference_hz'],window_seconds=n/rate,
            multiple20_40_flatness={ch:m['bands'][0]['channels'][ch]['whitened_flatness'] for ch in ['L','R']}))
    return dict(status='pass',anti_phase_tone_power=power_checks,exponential_pitch_peaks=peaks,
        pitch_error_sensitivity=sensitivity,
        sensitivity_scope='Stress controls, not estimated uncertainty of the recording ridge; common pitch estimation errors may leave dispersed structure. Do not classify the compensated recording as isolated noise.')


def figures(data):
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),constrained_layout=True)
    controls=data['controls']['signals'];names=list(controls)
    for j,w in enumerate(['1024','4096']):
        val=[controls[name][w]['bands'][1]['channels']['L']['whitened_flatness']['median'] for name in names]
        bars=axes[0].bar(np.arange(len(names))+(j-.5)*.34,val,.34,label=f'{int(w)/48000*1000:.1f} ms')
        axes[0].bar_label(bars,fmt='%.3f',padding=2,fontsize=8)
    axes[0].set(xticks=range(4),xticklabels=['White\nnoise','Coloured\nnoise','Fixed\nharmonics','Moving\nharmonics'],ylim=(0,1),ylabel='Whitened spectral flatness',title='Known controls / original 3-8 kHz / L')
    axes[0].legend()
    comp=data['controls']['known_compensation']['measurements']['12_cycles']['bands']
    val=[b['channels']['L']['whitened_flatness']['median'] for b in comp]
    axes[1].bar(range(3),val,color='#319d92')
    for i,v in enumerate(val):axes[1].text(i,v*1.4,f'{v:.4g}',ha='center',fontsize=9)
    axes[1].set(xticks=range(3),xticklabels=['2-10','10-20','20-40'],yscale='log',ylim=(1e-7,1),
        xlabel='Multiple of supplied known pitch',ylabel='Whitened spectral flatness (log scale)',
        title='Known compensation / 12 observed cycles\nChanged frequency bands; no physical-noise fraction')
    fig.savefig(OUT/'controls_resolution_log.png',dpi=150);plt.close(fig)
    # Sum of separate median powers; no assertion that coherent sources add.
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),constrained_layout=True)
    table=[]
    for load in [.18,.85]:
        air=[];exhaust=[];rpm=[]
        for r in [1200,2400,4000,6000,8000]:
            source=data['runtime'][f'rpm{r}_load{round(load*100)}_full']['sources']['source_median_3_8khz_mean_square']
            aa=10*np.log10(source['air_left']+source['air_right']);ee=10*np.log10(source['exhaust_left']+source['exhaust_right'])
            air.append(aa);exhaust.append(ee);rpm.append(r)
            table.append(dict(rpm=r,load=load,air_power_sum_dbfs=float(aa),exhaust_power_sum_dbfs=float(ee),air_to_exhaust_db=float(aa-ee)))
        axes[0].plot(rpm,air,'o--',label=f'Air L+R, load {load}')
        axes[0].plot(rpm,exhaust,'o-',label=f'Exhaust L+R, load {load}')
        axes[1].plot(rpm,np.array(air)-exhaust,'o-',label=f'load {load}')
    axes[0].set(xlabel='Engineering bench RPM',ylabel='Sum of separate source median powers / dBFS',title='Source excitation audit / original 3-8 kHz\nBefore spatial routing and master; not mixed power')
    axes[1].set(xlabel='Engineering bench RPM',ylabel='Air sum / exhaust sum / dB',title='Relative source balance changes with RPM\nNo recording RPM/load alignment assumed')
    for ax in axes:ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.savefig(OUT/'source_balance.png',dpi=150);plt.close(fig)
    with (OUT/'source_balance.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(table[0]));writer.writeheader();writer.writerows(table)
    return table


def main():
    destination=OUT/'supplement.json'
    if destination.exists():raise SystemExit('Preserve completed texture supplement.')
    data=json.loads((OUT/'results.json').read_text())
    result=dict(analytic_controls=analytic_controls(),source_balance=figures(data),
        primary_results_sha256=sha(OUT/'results.json'),tool_sha256=sha(ROOT/'tools/finalize_texture.py'))
    result['files']={name:sha(OUT/name) for name in ['controls_resolution_log.png','source_balance.png','source_balance.csv']}
    destination.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(result['analytic_controls'],indent=2))


if __name__=='__main__':main()
