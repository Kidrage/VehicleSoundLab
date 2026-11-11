"""Sampled continuous modal response versus its exact finite Nyquist series.

This is a controlled source-module diagnosis, not a real-recording comparison.
"""
import json
import subprocess
from runtime_review import ROOT,sha
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=ROOT/'renders/pressure_sampling_v1'
EXE=ROOT/'build-experiment-pressure-sampling/Release/pressure_sampling_probe.exe'
RATES=[16000,44100,48000,96000,192000]
RPMS=[1200,4000,8000]


def periodic_response(meta):
    rate=meta['sample_rate'];cycle=meta['cycle_hz'];t=np.arange(meta['frames'])/rate
    period=1/cycle;y=np.zeros((len(t),2))
    for event in meta['events']:
        elapsed=np.remainder(t-event['cycle_fraction']*period,period)
        for mode in meta['modes']:
            if not mode['enabled']:continue
            pole=-1/mode['decay_seconds']+2j*np.pi*mode['hz']
            # Exact sum of all previous impulses, no oversampled approximation.
            response=np.imag(np.exp(pole*elapsed)/(-np.expm1(pole*period)))
            y[:,event['bank']]+=meta['pressure_level']*event['strength']*mode['weight']*response
    return y


def finite_series(meta):
    rate=meta['sample_rate'];cycle=meta['cycle_hz'];n=meta['frames'];duration=n/rate
    cycles=round(duration*cycle);assert abs(cycles-duration*cycle)<1e-9
    orders=np.arange(int(np.floor(rate/(2*cycle)))+1);f=orders*cycle
    transfer=np.zeros(len(f),complex)
    for mode in meta['modes']:
        if not mode['enabled']:continue
        omega=2*np.pi*mode['hz'];alpha=1/mode['decay_seconds']
        transfer+=mode['weight']*omega/((alpha+2j*np.pi*f)**2+omega**2)
    coefficients=np.zeros((len(f),2),complex)
    for event in meta['events']:
        coefficients[:,event['bank']]+=event['strength']*np.exp(-2j*np.pi*orders*event['cycle_fraction'])
    coefficients*=cycle*meta['pressure_level']*transfer[:,None]
    spectrum=np.zeros((n,2),complex);spectrum[0]=coefficients[0]
    # Paired real-series terms; at exact Nyquist both land in the same bin.
    for k in range(1,len(orders)):
        index=k*cycles
        assert index<=n//2
        spectrum[index]+=coefficients[k];spectrum[-index]+=coefficients[k].conj()
    y=np.fft.ifft(spectrum,axis=0)*n
    assert abs(y.imag).max()<1e-12
    return y.real,coefficients


def ratio_db(numerator,denominator):
    if denominator<=0:return None
    if numerator==0:return None
    return float(10*np.log10(numerator/denominator))


def scores(actual,ideal,rate):
    delta=actual-ideal;n=len(actual);f=np.fft.rfftfreq(n,1/rate)
    fft_delta=np.fft.rfft(delta,axis=0)/n;fft_ideal=np.fft.rfft(ideal,axis=0)/n
    weight=np.full(len(f),2.);weight[0]=1
    if n%2==0:weight[-1]=1
    rows={}
    for name,lo,hi in [('AC',0,rate/2),('3000_8000',3000,min(8000,rate/2))]:
        mask=(f>lo)&(f<=hi);a=np.sum(abs(fft_delta[mask])**2*weight[mask,None],axis=0)
        b=np.sum(abs(fft_ideal[mask])**2*weight[mask,None],axis=0)
        rows[name]=dict(error_over_ideal_db_lr=[ratio_db(x,y) for x,y in zip(a,b)],
            error_power_lr=a.tolist(),ideal_power_lr=b.tolist())
    return dict(bands=rows,actual_mean_lr=actual.mean(axis=0).tolist(),ideal_mean_lr=ideal.mean(axis=0).tolist(),
        delta_peak_lr=abs(delta).max(axis=0).tolist(),
        meaning='Difference from an ideal brickwall Nyquist-limited version of this defined continuous source,including aliased harmonics. AC excludes DC. This ideal reference is noncausal and is not a proposed realtime filter or real-car timbre target.')


def controls():
    sr=48000;t=np.arange(sr)/sr
    low=.1*np.cos(2*np.pi*1100*t+.2);high=.03*np.cos(2*np.pi*(sr-1700)*t-.6)
    a=np.column_stack([low+high,.7*(low+high)]);b=np.column_stack([low,.7*low])
    observed=scores(a,b,sr);expected=20*np.log10(.03/.1)
    assert max(abs(v-expected) for v in observed['bands']['AC']['error_over_ideal_db_lr'])<1e-10
    shifted=scores(a+.37,b+.37,sr);scaled=scores(a*.31,b*.31,sr);swapped=scores(a[:,::-1],b[:,::-1],sr)
    for candidate in [shifted,scaled,swapped]:
        assert max(abs(v-expected) for v in candidate['bands']['AC']['error_over_ideal_db_lr'])<1e-10
    exact=scores(b,b,sr);assert all(v==0 for v in exact['delta_peak_lr'])
    return dict(known_out_of_band_tone_alias_ratio_db=expected,measured=observed,
        DC_offset_gain_and_channel_swap_invariance=True,identical_input_zero_error=True,
        limits='Designed analytic two-tone controls validate the error statistic; not car recordings.')


def main():
    if OUT.exists() and any(OUT.iterdir()):raise SystemExit('Preserve pressure_sampling_v1; use a new directory.')
    control=controls();OUT.mkdir(parents=True,exist_ok=True);runs={};examples={}
    for rate in RATES:
        for rpm in RPMS:
            name=f'{rate}_{rpm}';path=OUT/(name+'.wav')
            subprocess.run([str(EXE),str(path),str(rate),str(rpm)],check=True,capture_output=True,timeout=30)
            meta=json.loads(path.with_suffix('.wav.json').read_text());x,sr=sf.read(path,always_2d=True)
            assert sr==rate and sf.info(path).subtype=='FLOAT' and np.isfinite(x).all()
            exact=periodic_response(meta);error=float(abs(x-exact).max());assert error<2e-9,(name,error)
            ideal,coefficients=finite_series(meta);score=scores(x,ideal,rate)
            # Parseval AC provides a second, direct time-domain score calculation.
            direct=np.mean((x-ideal-(x-ideal).mean(axis=0))**2,axis=0)
            assert np.max(abs(direct-score['bands']['AC']['error_power_lr']))<1e-15
            ideal_path=OUT/(name+'_ideal.wav');sf.write(ideal_path,ideal,rate,subtype='FLOAT')
            runs[name]=dict(meta=meta,sampled_float_sha256=sha(path),ideal_float_sha256=sha(ideal_path),
                closed_form_vs_native_max_error=error,score=score,
                analytic_DC_lr=coefficients[0].real.tolist(),
                decay_at_warmup_upper_bound=float(np.exp(-.6/max(m['decay_seconds'] for m in meta['modes']))))
            if rpm==8000 and rate in [16000,48000]:examples[rate]=(x,ideal)
            print(name,'AC error/ideal:',score['bands']['AC']['error_over_ideal_db_lr'],flush=True)
    fig,axes=plt.subplots(1,2,figsize=(11,4.6),constrained_layout=True)
    for rpm in RPMS:
        values=[runs[f'{rate}_{rpm}']['score']['bands']['AC']['error_over_ideal_db_lr'][0] for rate in RATES]
        axes[0].plot(np.array(RATES)/1000,values,'o-',label=f'{rpm} engineering RPM / L')
    axes[0].set(xlabel='Sample rate / kHz',ylabel='Sampling error / ideal AC power, dB',title='Defined pressure module; constant event strengths')
    x,ideal=examples[48000];N=len(x);f=np.fft.rfftfreq(N,1/48000)
    for y,label in [(ideal,'Ideal Nyquist-limited'),(x-ideal,'Native minus ideal')]:
        amplitude=abs(np.fft.rfft(y[:,0]))/N
        axes[1].plot(f,20*np.log10(np.maximum(amplitude,1e-15)),lw=.8,label=label)
    axes[1].set(xlim=(0,24000),ylim=(-160,-35),xlabel='Frequency / Hz',ylabel='DFT coefficient / dBFS',title='8000 engineering RPM,48kHz,L; no master/IR')
    for ax in axes:ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.savefig(OUT/'pressure_sampling.png',dpi=160);plt.close(fig)
    sources=[ROOT/'tools/analyze_pressure_sampling.py',*(ROOT/'experiments/pressure_sampling_v1').glob('*')]
    result=dict(schema='vsl.pressure-sampling/1',native_runtime='0.17.0 unchanged',controls=control,runs=runs,
        sources={p.relative_to(ROOT).as_posix():sha(p) for p in sources if p.is_file()},
        inputs={p.relative_to(ROOT).as_posix():sha(p) for p in [EXE,ROOT/'baselines/v0.17.0/bin/vsl_core.lib',ROOT/'baselines/v0.17.0/manifest.json']},
        files={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file()},
        scope='Constant-strength unmodulated native pressure module,three engineering RPMs,five sample rates. Closed-form continuous periodic response and finite Nyquist harmonic series share actual C coefficients/geometry. No random modulation,full engine,drive,bank propagation,IR,listener,reference download or perceptual acceptance. DC reported separately; no error percentage claimed.')
    (OUT/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')


if __name__=='__main__':main()
