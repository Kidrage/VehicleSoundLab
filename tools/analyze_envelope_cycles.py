"""Observe phase-conditioned band envelopes without native voicing edits."""
import csv
import json
from dataclasses import asdict
from runtime_review import ROOT, sha
from reference_segments import read_segment
from envelope_cycles import EnvelopeSettings, band_analytic, remove_slow_log_trend, power_grid, score
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=ROOT/'references/analysis/envelope_cycles_detrended_v1'
TRACKS=ROOT/'references/analysis/rev_descent_v1/results.json'
BANDS=[(1200,3000),(3000,8000)]
DIVISORS=[1,5]
HARMONICS=[8,16]
SETTINGS=EnvelopeSettings()


def measures(audio,rate,times,frequency,origin=0,divisors=DIVISORS):
    result=[];grids={}
    for band in BANDS:
        raw=band_analytic(audio,rate,band,SETTINGS)
        mask=(origin+np.arange(len(raw))/rate>=times[0])&(origin+np.arange(len(raw))/rate<=times[-1])
        raw_mean=np.mean(abs(raw[mask])**2,axis=0)
        if np.min(raw_mean)<SETTINGS.minimum_raw_mean_power:
            result.extend(dict(band_hz=list(band),divisor=d,harmonics=h,status='unmeasured',
                raw_analytic_power_db_lr=(10*np.log10(np.maximum(raw_mean,1e-30))).tolist(),
                reason='Raw band below declared -160 dB analytic-power floor; do not normalize silence') for d in divisors for h in HARMONICS)
            continue
        analytic=remove_slow_log_trend(raw,rate,SETTINGS)
        for divisor in divisors:
            try:
                power,meta,inverse=power_grid(analytic,rate,times,frequency,divisor,origin,SETTINGS)
            except ValueError as error:
                result.extend(dict(band_hz=list(band),divisor=divisor,harmonics=h,status='unmeasured',reason=str(error)) for h in HARMONICS)
                continue
            for harmonics in HARMONICS:
                row=score(power,inverse,harmonics,SETTINGS)
                result.append(dict(band_hz=list(band),divisor=divisor,grid=meta,**row))
                result[-1]['harmonics']=harmonics
                result[-1]['raw_analytic_power_db_lr']=(10*np.log10(raw_mean)).tolist()
            if band==(3000,8000) and divisor==1:grids['high_observed_period']=(power,inverse)
    return result,grids


def control_runs():
    rate=48000;t=np.arange(6*rate)/rate
    times=np.arange(.2,5.8,.002);frequency=np.full(len(times),100.)
    phase=2*np.pi*100*t
    modulation=1+.80*np.cos(phase)+.15*np.sin(2*phase)
    rng=np.random.default_rng(48271)
    white=rng.normal(0,.04,(len(t),2))
    waves={
        'unmodulated_noise':white,
        'phase_modulated_noise':white*np.sqrt(modulation[:,None]),
        'deterministic_AM_tone':np.sqrt(modulation[:,None])*.04*np.column_stack([np.cos(2*np.pi*5500*t),np.sin(2*np.pi*5500*t)]),
        'single_tone':.04*np.column_stack([np.cos(2*np.pi*5500*t),np.sin(2*np.pi*5500*t)]),
        'deterministic_additive_OSC':sum(.02/np.sqrt(k)*np.column_stack([np.cos(k*phase+.13*k),np.sin(k*phase+.13*k)]) for k in range(32,79)),
    }
    results={};display={}
    for name,x in waves.items():
        z=remove_slow_log_trend(band_analytic(x,rate,(3000,8000),SETTINGS),rate,SETTINGS)
        power,meta,inverse=power_grid(z,rate,times,frequency,settings=SETTINGS)
        row=score(power,inverse,8,SETTINGS);results[name]=dict(grid=meta,**row)
        if name=='phase_modulated_noise':display[name]=(power,inverse)
    assert results['single_tone']['status']=='unmeasured'
    assert max(results['deterministic_AM_tone']['future_envelope_error_db_lr'])<-55
    # A narrow periodic impulse-like envelope has harmonics above8. Its error
    # must reach the independent truncation floor, not an invented dB target.
    additive=results['deterministic_additive_OSC']
    assert np.max(abs(np.array(additive['future_envelope_error_db_lr'])-
                      additive['per_test_cycle_harmonic_projection_floor_db_lr']))<1e-6
    assert max(abs(np.array(results['unmodulated_noise']['phase_contrast_db_lr'])))<.2
    assert min(results['phase_modulated_noise']['phase_contrast_db_lr'])>.5
    # Linear chirp has an exact piecewise-linear frequency path. Check the
    # interpolated analytic envelope against its independent closed form.
    chirp_phase=2*np.pi*(80*t+10*t*t)
    chirp_power=1+.6*np.cos(chirp_phase)+.15*np.sin(2*chirp_phase)
    x=np.sqrt(chirp_power[:,None])*.04*np.column_stack([np.cos(2*np.pi*5500*t),np.sin(2*np.pi*5500*t)])
    z=remove_slow_log_trend(band_analytic(x,rate,(3000,8000),SETTINGS),rate,SETTINGS)
    power,meta,inverse=power_grid(z,rate,times,80+20*times,settings=SETTINGS)
    exact_phase=2*np.pi*(80*inverse+10*inverse*inverse)
    exact=1+.6*np.cos(exact_phase)+.15*np.sin(2*exact_phase)
    # The slow geometric level is conditioned out; compare cycle-normalized
    # shape to the analytic AM shape independently of that nuisance level.
    exact=exact/exact.mean(axis=1,keepdims=True)
    normalized=power/power.mean(axis=1,keepdims=True)
    error=float(10*np.log10(np.mean((normalized-exact[:,:,None])**2)/np.mean(exact**2)))
    assert error<-55,error
    results['analytic_AM_chirp']=dict(grid=meta,analytic_envelope_error_db=error,**score(power,inverse,8,SETTINGS))
    # Deterministic changing fixed-Hz spectrum is another mechanism for
    # changing envelopes. It is never labelled as measured random events.
    alpha=np.log(1.7)/6;f=160*np.exp(-alpha*t)
    chirp_phase=2*np.pi*160*(1-np.exp(-alpha*t))/alpha
    x=np.zeros((len(t),2))
    for k in range(1,129):
        amplitude=.02/np.sqrt(k)*(.01+np.exp(-((k*f-3870)/160)**2))
        x[:,0]+=amplitude*np.cos(k*chirp_phase+.13*k)
        x[:,1]+=amplitude*np.sin(k*chirp_phase+.13*k)
    z=remove_slow_log_trend(band_analytic(x,rate,(3000,8000),SETTINGS),rate,SETTINGS)
    power,meta,inverse=power_grid(z,rate,times,160*np.exp(-alpha*times),settings=SETTINGS)
    results['changing_fixed_Hz_noiseless_OSC']=dict(grid=meta,**score(power,inverse,8,SETTINGS))
    # Explicit confound and correction: an arbitrary supplied100 Hz clock
    # makes a smooth exponential fade look like repeated within-cycle ramps.
    x=.04*np.exp(-.4*t[:,None])*np.column_stack([np.cos(2*np.pi*5500*t),np.sin(2*np.pi*5500*t)])
    raw=band_analytic(x,rate,(3000,8000),SETTINGS)
    p,_,inverse=power_grid(raw,rate,times,frequency,settings=SETTINGS)
    raw_result=score(p,inverse,8,SETTINGS)
    z=remove_slow_log_trend(raw,rate,SETTINGS)
    p,_,inverse=power_grid(z,rate,times,frequency,settings=SETTINGS)
    corrected=score(p,inverse,8,SETTINGS)
    assert min(raw_result['phase_contrast_db_lr'])>5
    assert corrected['status']=='unmeasured',corrected
    results['smooth_fade_arbitrary_clock']=dict(initial_cycle_mean_only=raw_result,
        finite_log_trend_removed=corrected,
        meaning='An imposed cycle clock plus smooth level decay can fake phase-linked envelope shape. The corrected constant envelope is uninformative.')
    return dict(settings=asdict(SETTINGS),signals=results),display


def native_runs():
    native=json.loads((ROOT/'renders/v0.16.0/verification.json').read_text())
    tap_manifest=json.loads((ROOT/'renders/exhaust_envelope_v1/results.json').read_text())
    result={};inputs={};display={}
    for case,rpm in [('low',1200),('mid',4000),('high',8000)]:
        tags=['base','combined'] if case!='mid' else ['base','pressure','structure','combined']
        for tag in tags:
            path=ROOT/f'renders/v0.16.0/{case}_{tag}.wav'
            assert sha(path)==native['files'][path.name]
            inputs[path.relative_to(ROOT).as_posix()]=sha(path)
            audio,rate=sf.read(path,always_2d=True);assert sf.info(path).subtype=='FLOAT'
            times=np.arange(2.5,4.8,.005);frequency=np.full(len(times),rpm*10/240.)
            rows,grid=measures(audio,rate,times,frequency)
            key=f'{case}_{tag}_mix';result[key]=dict(known_engineering_rpm=rpm,
                channels='Stereo listener L/R',input=path.relative_to(ROOT).as_posix(),measurements=rows,
                coordinate='Model bank rate=RPM*10/240; divisor5 is its full720-degree cycle. Not matched to reference recording conditions.')
            if key=='mid_base_mix':display[key]=grid['high_observed_period']
        if case in ['mid','high']:
            path=ROOT/f'renders/exhaust_envelope_v1/{case}_base_fired_input.wav'
            assert sha(path)==tap_manifest['files'][path.name]
            inputs[path.relative_to(ROOT).as_posix()]=sha(path)
            audio,rate=sf.read(path,always_2d=True)
            rows,_=measures(audio,rate,times,frequency)
            result[f'{case}_fired_input']=dict(known_engineering_rpm=rpm,
                channels='Two independent physical bank taps, before pumping/character additions and spatial rendering',
                input=path.relative_to(ROOT).as_posix(),measurements=rows)
        print('native envelopes',case,flush=True)
    path=ROOT/'renders/exhaust_envelope_v1/neutral_base_fired_input.wav'
    assert sha(path)==tap_manifest['files'][path.name];inputs[path.relative_to(ROOT).as_posix()]=sha(path)
    audio,rate=sf.read(path,always_2d=True)
    trace=ROOT/'renders/v0.16.0/neutral_base.vsltake.csv'
    inputs[trace.relative_to(ROOT).as_posix()]=sha(trace)
    with trace.open(newline='') as file:states=list(csv.DictReader(file))
    for label,(start,stop),fuel_mode in [('neutral_fired',(3.,4.2),'FIRE'),('neutral_cut',(6.45,7.85),'CUT')]:
        selected=[row for row in states if start<=float(row['seconds'])<=stop]
        assert selected and all(row['fuel_mode']==fuel_mode for row in selected)
        times=np.array([float(row['seconds']) for row in selected])
        frequency=np.array([float(row['rpm'])*10/240 for row in selected])
        rows,_=measures(audio,rate,times,frequency)
        result[label]=dict(input=path.relative_to(ROOT).as_posix(),fuel_mode=fuel_mode,measurements=rows,
            channels='Two physical fired-pressure bank taps',
            coordinate='Piecewise-linear rate from rounded 200 Hz audio-clock trace; not exact crank phase or measured vehicle RPM.')
    return result,inputs,display


def reference_runs():
    audio,rate,provenance=read_segment('A_exterior_blips','exterior_dynamic_observation')
    saved=json.loads(TRACKS.read_text());assert saved['reference']['master_sha256']==provenance['master_sha256']
    names=['first_upper_80ms_mean_power','first_upper_128ms_mean_power','first_upper_192ms_mean_power','second_upper_128ms_mean_power']
    result={};display={}
    for name in names:
        path=saved['runs'][name];assert path['status']=='connected_peak_path' and path['support_fraction']==1
        times=np.array([row['seconds'] for row in path['rows']]);frequency=np.array([row['hz'] for row in path['rows']])
        rows,grid=measures(audio,rate,times,frequency,provenance['source_seconds'][0])
        result[name]=dict(reference=provenance,path_support=path['support_fraction'],source_seconds=[times[0],times[-1]],
            observed_frequency_endpoints_hz=[frequency[0],frequency[-1]],measurements=rows,
            coordinate='Full saved offline ridge conditioned on; repeat divisors1/5 are hypotheses, not identified crank/bank orders or physical RPM.',
            channels='Original mixed-recording microphone L/R, kept separate')
        if name=='first_upper_128ms_mean_power':display[name]=grid['high_observed_period']
        print('reference envelopes',name,flush=True)
    return result,display


def main():
    if (OUT/'results.json').exists():raise SystemExit('Preserve completed envelope_cycles_v1.')
    OUT.mkdir(parents=True,exist_ok=True)
    controls,examples=control_runs();print('analytic and noise controls passed',flush=True)
    reference,ref_examples=reference_runs();examples.update(ref_examples)
    runtime,inputs,native_examples=native_runs();examples.update(native_examples)
    summaries=[]
    for group,items in [('reference',reference),('native',runtime)]:
        for name,item in items.items():
            for row in item['measurements']:
                if row['status']=='measured':
                    summaries.append(dict(group=group,name=name,band_low_hz=row['band_hz'][0],band_high_hz=row['band_hz'][1],
                        divisor=row['divisor'],harmonics=row['harmonics'],held_out_cycles=row['held_out_cycles'],
                        L_error_db=row['future_envelope_error_db_lr'][0],R_error_db=row['future_envelope_error_db_lr'][1],
                        L_projection_floor_db=row['per_test_cycle_harmonic_projection_floor_db_lr'][0],R_projection_floor_db=row['per_test_cycle_harmonic_projection_floor_db_lr'][1],
                        L_phase_contrast_db=row['phase_contrast_db_lr'][0],R_phase_contrast_db=row['phase_contrast_db_lr'][1]))
    with (OUT/'summary.csv').open('w',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=list(summaries[0]));writer.writeheader();writer.writerows(summaries)
    fig,axes=plt.subplots(1,3,figsize=(13,4.7),constrained_layout=True)
    for ax,(name,(power,inverse)) in zip(axes,examples.items()):
        shape=power/power.mean(axis=1,keepdims=True)-1
        first=max(0,len(shape)//2-10);selected=shape[first:first+20,:,0]
        # Low-harmonic display uses the same16-harmonic projection for all.
        transformed=np.fft.rfft(selected,axis=1);transformed[:,17:]=0
        display=np.fft.irfft(transformed,n=selected.shape[1],axis=1)
        image=ax.imshow(display,aspect='auto',origin='lower',extent=[0,1,first,first+len(display)],vmin=-1,vmax=2,cmap='magma')
        ax.set(title=name.replace('_',' ')+'\n3-8 kHz, channel1',xlabel='Supplied observed-period phase',ylabel='Complete cycle index')
        np.savez_compressed(OUT/f'{name}_grid.npz',power=power,inverse_seconds=inverse)
    fig.colorbar(image,ax=axes,label='Detrended cycle-normalized analytic power minus1 (16 harmonics for display)')
    fig.savefig(OUT/'envelope_cycles.png',dpi=160);plt.close(fig)
    result=dict(schema='vsl.envelope-cycles/1',runtime='0.16.0 unchanged',settings=asdict(SETTINGS),
        controls=controls,reference=reference,native=runtime,inputs=inputs,
        initial_cycle_mean_only=dict(path='references/analysis/envelope_cycles_v1/results.json',
            sha256=sha(ROOT/'references/analysis/envelope_cycles_v1/results.json'),
            status='Retained initial analysis before identifying the slow-level ramp confound; source copies in initial_sources/tools.'),
        ridge_source=dict(path=TRACKS.relative_to(ROOT).as_posix(),sha256=sha(TRACKS)),
        source_files={name:sha(ROOT/name) for name in ['tools/envelope_cycles.py','tools/analyze_envelope_cycles.py','tools/cycle_prediction.py','tools/reference_segments.py']},
        definitions=dict(observable='Centred513-tap complex FIR band, remove finite Gaussian log-power trend (sigma20 ms, truncate4 = +/-80 ms) then analytic power; each complete supplied cycle/channel divided by its own equal-phase mean. Raw band floor checked before normalization. No raw-time power fraction or waveform reconstruction.',
            prediction='Past8 complete cycles, at least200 ms endpoint gap, next4 disjoint cycles; phase harmonics8/16, no held-out template gain/phase fitting. Future slow trend, cycle means and complete observed ridge are conditioned on, not predicted. No overlap of finite raw analysis supports across the gap.',
            phase_contrast='64 independently shifted held-out cycles, one shift shared by both channels; fixed past template. Quantiles are designed perturbation outcomes, not confidence intervals, physical null probabilities or source fractions.',
            limits='Unknown reference order/RPM/load, fixed-Hz transfer, path error, other sources, environment and encoding confounded. Phase-linked energy need not be stochastic combustion or mechanics; additive OSC can produce it. Steady native and swept reference are not matched vehicle conditions.'),
        subjective='No new voicing, normalization, audio derivative, reference playback in core or listening acceptance.')
    result['files']={p.name:sha(p) for p in OUT.iterdir() if p.is_file()}
    (OUT/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(result='measured',reference_runs=len(reference),native_cases=len(runtime),measured_rows=len(summaries),
        control_summary={k:{f:r.get(f) for f in ['status','future_envelope_error_db_lr','phase_contrast_db_lr']} for k,r in controls['signals'].items()}),indent=2))


if __name__=='__main__':main()
