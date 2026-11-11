"""Controlled spectral-density and observed-ridge compensation investigation."""
import csv
import json
from pathlib import Path
from runtime_review import ROOT,sha
from reference_segments import read_segment
from texture_metrics import measure,TextureSettings
from pitch_warp import compensate
from ridge_tracks import RidgeSettings,spectrogram,follow
import numpy as np
import soundfile as sf
from scipy import signal
from scipy.fft import next_fast_len
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=ROOT/'references/analysis/texture_v1'
RATE=48000
WINDOWS=[1024,4096]
REFERENCES=[('A_low','A_exterior_low_rev','exterior_spectral_observation'),
    ('A_blips','A_exterior_blips','exterior_dynamic_observation'),
    ('A_moving','A_exterior_moving','exterior_dynamic_observation'),
    ('B_cabin','B_cabin_pull','interior_channel_observation')]
ORDER_BANDS=[(2,10),(10,20),(20,40)]


def json_write(name,obj):
    (OUT/name).write_text(json.dumps(obj,indent=2,allow_nan=False),encoding='utf-8')


def write_series(path,data,origin=0,inverse=None):
    columns=[];values=[]
    for band,items in data['values'].items():
        for key,val in items.items():
            for c,channel in enumerate(['L','R']):columns.append(f'{band}_{channel}_{key}');values.append(val[c])
    t=data['seconds']
    source=np.interp(t,inverse['normalized_seconds'],inverse['source_seconds']) if inverse else t+origin
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['analysis_seconds','source_seconds',*columns]);w.writerows(zip(t,source,*values))


def collect(x,name,origin=0,bands=None,settings=None,inverse=None,normalized_reference=None):
    result={}
    windows=[(str(w),w,256) for w in WINDOWS]
    if normalized_reference:
        windows=[(f'{cycles}_cycles',next_fast_len(round(cycles*RATE/normalized_reference)),None) for cycles in [4,12]]
    for label,window,hop in windows:
        opt=TextureSettings(window=window,hop=hop or round(window/16),envelope_sigma_hz=settings.envelope_sigma_hz if settings else 500)
        m,s=measure(x,RATE,opt,**({'bands':bands} if bands else {}))
        result[label]=m
        write_series(OUT/f'{name}_{label}.csv',s,origin,inverse)
    return result


def controls():
    rng=np.random.default_rng(48271);t=np.arange(4*RATE)/RATE
    noise=rng.normal(0,.06,size=(len(t),2))
    colour=signal.sosfilt(signal.butter(4,[1800,6500],btype='bandpass',fs=RATE,output='sos'),noise,axis=0)
    signals={'white_noise':noise,'coloured_noise':colour}
    f=120+80*np.sin(2*np.pi*1.5*t)
    moving_phase=2*np.pi*120*t+80/1.5*(1-np.cos(2*np.pi*1.5*t))
    for moving,name in [(False,'fixed_harmonics'),(True,'moving_harmonics')]:
        frequency=f if moving else np.full(len(t),120.)
        phase=moving_phase if moving else 2*np.pi*120*t
        x=np.zeros((len(t),2))
        for k in range(1,101):
            amp=.008*np.exp(-((k*frequency-5000)/2500)**2)
            for c in range(2):x[:,c]+=amp*np.cos(k*phase+.17*k+.11*c*k)
        signals[name]=x
    results={name:collect(x,'control_'+name) for name,x in signals.items()}
    # Exact known pitch law, not the recording's uncertain estimated ridge.
    index=np.arange(round(.1*RATE),round(3.9*RATE),48)
    warped,meta,inverse=compensate(signals['moving_harmonics'],RATE,t[index],f[index])
    bands=[(a*meta['reference_hz'],b*meta['reference_hz']) for a,b in ORDER_BANDS]
    compensated=collect(warped,'control_compensated',bands=bands,
        settings=TextureSettings(envelope_sigma_hz=3*meta['reference_hz']),inverse=inverse,normalized_reference=meta['reference_hz'])
    # Meaningful invariants and interpolation check on a high-frequency tone.
    original=measure(signals['moving_harmonics'],RATE)[0]
    swap=measure(signals['moving_harmonics'][:,::-1],RATE)[0]
    gain=measure(signals['moving_harmonics']*.31,RATE)[0]
    gain_errors=[]
    for a,b,c in zip(original['bands'],swap['bands'],gain['bands']):
        for ch,other in [('L','R'),('R','L')]:
            for key in ['flatness','whitened_flatness','effective_bin_fraction','strongest_8_lobes_fraction']:
                assert a['channels'][ch][key]==b['channels'][other][key]
                gain_errors.append(abs(a['channels'][ch][key]['median']-c['channels'][ch][key]['median']))
    assert max(gain_errors)<1e-10
    hi=np.column_stack((.2*np.cos(2*np.pi*14000*t+.3),.13*np.cos(2*np.pi*14000*t-.7)))
    actual,tone_meta,mapping=compensate(hi,RATE,t[index],f[index])
    exact=np.column_stack((.2*np.cos(2*np.pi*14000*mapping['source_seconds']+.3),.13*np.cos(2*np.pi*14000*mapping['source_seconds']-.7)))
    error_db=float(10*np.log10(np.mean((actual-exact)**2)/np.mean(exact**2)))
    assert error_db<-50
    swapped,_,_=compensate(signals['moving_harmonics'][:,::-1],RATE,t[index],f[index])
    assert np.array_equal(swapped,warped[:,::-1])
    fixed_long=results['fixed_harmonics']['4096']['bands'][1]['channels']['L']['whitened_flatness']['median']
    moving_long=results['moving_harmonics']['4096']['bands'][1]['channels']['L']['whitened_flatness']['median']
    noise_long=results['white_noise']['4096']['bands'][1]['channels']['L']['whitened_flatness']['median']
    assert fixed_long<.02 and moving_long>.3 and .45<noise_long<.7
    compensated_high=compensated['12_cycles']['bands'][2]['channels']['L']['whitened_flatness']['median']
    assert compensated_high<.1
    result=dict(signals=results,known_compensation=dict(metadata=meta,observed_multiple_bands=ORDER_BANDS,measurements=compensated),
        checks=dict(channel_swap_exact=True,warp_channel_swap_exact=True,max_gain_invariance_error=max(gain_errors),
            resampler_14khz_waveform_error_db=error_db,compensated_multiple20_40_flatness=compensated_high),
        meaning='Known pure harmonic sweep may have noise-like STFT flatness; this is a counterexample to physical-noise classification, not a noise-percentage estimator.')
    fig,axes=plt.subplots(1,2,figsize=(12,4),constrained_layout=True)
    names=list(results);pos=np.arange(len(names))
    for j,window in enumerate(WINDOWS):
        vals=[results[n][str(window)]['bands'][1]['channels']['L']['whitened_flatness']['median'] for n in names]
        axes[0].bar(pos+(j-.5)*.34,vals,.34,label=f'{window/RATE*1000:.1f} ms')
    axes[0].set(xticks=pos,xticklabels=['White\nnoise','Coloured\nnoise','Fixed\nharmonics','Moving\nharmonics'],ylabel='Whitened spectral flatness',ylim=(0,1),title='Known controls: original 3-8 kHz, L')
    axes[0].legend()
    vals=[compensated['12_cycles']['bands'][i]['channels']['L']['whitened_flatness']['median'] for i in range(3)]
    axes[1].bar(range(3),vals,color='#319d92')
    axes[1].set(xticks=range(3),xticklabels=['2-10','10-20','20-40'],xlabel='Multiple of supplied known pitch',ylabel='Whitened spectral flatness',ylim=(0,1),title='After known pitch compensation, 12 observed cycles\nChanged frequency coordinate; not the same Hz bands')
    fig.savefig(OUT/'controls_resolution.png',dpi=150);plt.close(fig)
    return result


def source_audit(prefix):
    rows={}
    for path in sorted(prefix.parent.glob(prefix.name+'_source_*.wav')):
        x,rate=sf.read(path);assert rate==RATE and x.ndim==1 and sf.info(path).subtype=='FLOAT'
        x=x[round(2.5*rate):round(5.8*rate)]
        hz,_,z=signal.stft(x,rate,nperseg=4096,noverlap=3840,boundary=None,padded=False,scaling='psd')
        p=abs(z)**2;mask=(hz>=3000)&(hz<8000)
        energy=np.median(p[mask].sum(axis=0)*2*rate/4096)
        rows[path.stem.split('_source_')[-1]]=float(energy)
    assert len(rows)==10
    return dict(source_median_3_8khz_mean_square=rows,
        scope='Pre-master independent object powers. Powers of correlated objects do not add to mixed power; routing gains/interference are absent. Not physical acoustic watts or mix percentages.')


def reference_compensation(x,origin):
    results={};warps={};paths={}
    for window in [.08,.128,.192]:
        opt=RidgeSettings(window_seconds=window)
        hz,t,p=spectrogram(x,RATE,opt);t+=origin
        path=follow(hz,t,p.mean(axis=1),238.18,239.00,315,opt)
        assert path['status']=='connected_peak_path' and path['support_fraction']>.99
        rows=path['rows'];freq=np.array([r['hz'] for r in rows]);ts=np.array([r['seconds'] for r in rows])
        warped,meta,inverse=compensate(x,RATE,ts,freq,origin)
        bands=[(a*meta['reference_hz'],b*meta['reference_hz']) for a,b in ORDER_BANDS]
        label=f'{round(window*1000)}ms'
        measured=collect(warped,'reference_compensated_'+label,bands=bands,
            settings=TextureSettings(envelope_sigma_hz=3*meta['reference_hz']),inverse=inverse,normalized_reference=meta['reference_hz'])
        results[label]=dict(path_settings=opt.__dict__,path=path,metadata=meta,
            observed_multiple_bands=ORDER_BANDS,measurements=measured)
        warps[label]=(warped,meta,inverse);paths[label]=(ts,freq)
    y,meta,_=warps['128ms'];ts,f=paths['128ms']
    fig,axes=plt.subplots(2,1,figsize=(12,7),constrained_layout=True)
    for ax,a,normalized in [(axes[0],x[round((ts[0]-origin)*RATE):round((ts[-1]-origin)*RATE)],False),(axes[1],y,True)]:
        hz,t,z=signal.stft(a,RATE,nperseg=4096,noverlap=3840,boundary=None,padded=False,scaling='psd',axis=0)
        psd=(abs(z)**2).mean(axis=1)
        axis=hz/meta['reference_hz'] if normalized else hz
        ax.pcolormesh(t if normalized else t+ts[0],axis,10*np.log10(np.maximum(psd,1e-30)),shading='auto',cmap='magma',vmin=-90,vmax=-25,rasterized=True)
        ax.set(ylim=(2,40) if normalized else (300,12500),
            ylabel='Multiple of observed ridge' if normalized else 'Original frequency / Hz',
            xlabel='Normalized seconds (time changed)' if normalized else 'Original source seconds',
            title='Same stereo time map, observed-ridge coordinate; no physical engine-order label' if normalized else 'A first descent: frequency sweep broadens high-frequency lines')
    fig.savefig(OUT/'reference_pitch_compensation.png',dpi=150);plt.close(fig)
    return dict(selection='Prior supported first-upper ridge, canonical A 238-248 s; source frame centres 238.18-239.00. No neutral, pedal-release or RPM label.',
        sensitivity='80/128/192 ms analysis windows and explicit common-channel inverse maps; not independent trials or confidence intervals.',
        runs=results)


def overview(refs,runtime):
    fig,axes=plt.subplots(2,2,figsize=(13,9),constrained_layout=True)
    for col,window in enumerate(WINDOWS):
        for c,ch in enumerate(['L','R']):
            vals=[refs[n]['measurements'][str(window)]['bands'][1]['channels'][ch]['whitened_flatness'] for n in refs]
            med=np.array([v['median'] for v in vals]);lo=np.array([v['p10'] for v in vals]);hi=np.array([v['p90'] for v in vals])
            axes[0,col].errorbar(np.arange(len(refs))+(c-.5)*.12,med,yerr=[med-lo,hi-med],fmt='o',capsize=3,label=ch)
        axes[0,col].set(xticks=range(len(refs)),xticklabels=list(refs),ylim=(0,1),ylabel='Whitened spectral flatness',title=f'Recordings, original 3-8 kHz / {window/RATE*1000:.1f} ms\n10-90% frame range, not a confidence interval')
        axes[0,col].legend()
        for load,pure in [(.18,False),(.85,False),(.85,True)]:
            rows=sorted([v for v in runtime.values() if v['parameters']['load']==load and v['parameters']['pure_osc']==pure],key=lambda v:v['parameters']['rpm'])
            for ch,style in [('L','-'),('R','--')]:
                axes[1,col].plot([v['parameters']['rpm'] for v in rows],[v['measurements'][str(window)]['bands'][1]['channels'][ch]['whitened_flatness']['median'] for v in rows],style,marker='.',label=f'{"OSC" if pure else "Full"} load {load} {ch}')
        axes[1,col].set(ylim=(0,1),xlabel='Engineering bench RPM',ylabel='Whitened spectral flatness',title='Frozen V015, stable 2.5-5.8 s\nReference RPM/load and acoustic transfer unmatched')
        axes[1,col].legend(ncol=2,fontsize=8)
    fig.savefig(OUT/'recordings_and_runtime.png',dpi=150);plt.close(fig)


def main():
    if (OUT/'results.json').exists():raise SystemExit('Preserve completed texture investigation.')
    probes=json.loads((OUT/'probes.json').read_text())
    controls_result=controls();print('Known controls and compensation verified.',flush=True)
    refs={};blips=None
    for name,segment,use in REFERENCES:
        x,rate,provenance=read_segment(segment,use);assert rate==RATE
        refs[name]=dict(provenance=provenance,measurements=collect(x,name,provenance['source_seconds'][0]))
        if name=='A_blips':blips=x
        print('Measured',name,flush=True)
    motion=reference_compensation(blips,238);print('Compensated supported A ridge with three window estimates.',flush=True)
    runtime={}
    for name,params in probes['cases'].items():
        x,rate=sf.read(OUT/'runtime'/f'{name}.wav',always_2d=True);assert rate==RATE
        lo,hi=params['measurement_interval_seconds'];x=x[round(lo*rate):round(hi*rate)]
        runtime[name]=dict(parameters=params,measurements=collect(x,name,lo),sources=source_audit(OUT/'runtime'/name))
        print('Measured',name,flush=True)
    overview(refs,runtime)
    path=ROOT/'research/upstream/gen/v10_powertrain.gendsp'
    text=json.loads(path.read_text())
    code=text['patcher']['boxes'][0]['box'].get('code','')
    if not code:
        def find(node):
            if isinstance(node,dict):
                if node.get('maxclass')=='codebox':yield node.get('code','')
                for v in node.values():yield from find(v)
            elif isinstance(node,list):
                for v in node:yield from find(v)
        code='\n'.join(find(text))
    upstream_lines=[line for line in code.splitlines() if line.startswith(('bright_l =','bright_r =','residual_l =','residual_r ='))]
    assert len(upstream_lines)==4
    result=dict(schema='vsl.texture-observations/1',runtime_version='0.15.0',controls=controls_result,
        references=refs,reference_compensation=motion,runtime=runtime,
        upstream=dict(revision='ac2b37d8639027d79934a2023cf8d1d37d3b2f96',snapshot_sha256=sha(path),exact_lines=upstream_lines,
            interpretation='Named bright/residual V6 layers here use oscillators and pulse modulation; the names do not identify measured stochastic noise.'),
        definitions=dict(analysis='Per-channel native-grid Hann STFT; no zero padding. Raw and 500 Hz sigma frequency-whitened power distributions. Eight disjoint +/-2-bin supports measure concentration, not oscillator energy.',
            reference_processing='Unchanged float32 stereo through canonical reader. Pitch-warped arrays are offline diagnostic transformations only; no transformed reference WAV or runtime source playback.',
            metric_scope='Spectral flatness, effective-bin fraction and concentration are descriptive. Neither 1-flatness nor 1-concentration is a physical noise fraction or realism score.',
            motion_scope='Normalized observed-ridge multiples, not physical order; pitch warping changes time and frequency bands. Never compare normalized-band power with unchanged original-Hz band power.',
            comparison_scope='C grid has known engineering RPM/load; reference has unknown RPM/load/transfer/codec. No fitted Lamborghini model or matched-state error score.'),
        files={str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='results.json'})
    json_write('results.json',result)
    print('Texture investigation complete.',flush=True)


if __name__=='__main__':main()
