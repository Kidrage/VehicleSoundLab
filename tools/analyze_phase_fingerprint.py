"""Approved mixed-reference phase observations and explicitly local DNA."""
import json
from dataclasses import replace
from runtime_review import ROOT,sha
from reference_segments import read_segment
from ridge_tracks import RidgeSettings,spectrogram,follow
from phase_fingerprint import PhaseFitSettings,fit,complex_coefficients,curvature,transfer_check,dna_text,integrated_cycles
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=ROOT/'references/analysis/phase_fingerprint_v1'


def controls():
    rate=48000;t=np.arange(2*rate)/rate;times=np.linspace(0,t[-1],300)
    frequency=80+15*times;phase=2*np.pi*(80*t+7.5*t*t)
    orders=np.arange(1,41);z=np.column_stack([.05/np.sqrt(orders)*np.exp(1j*(.17*orders+.07*orders**2)),
        .04/np.sqrt(orders)*np.exp(1j*(-.13*orders+.04*orders**2))])
    x=np.real(np.exp(1j*phase[:,None]*orders[None,:])@z)
    settings=PhaseFitSettings(maximum_harmonics=40)
    records=[fit(x,rate,0,times,frequency,center,settings) for center in [.4,1.2]]
    errors=[]
    for center,row in zip([.4,1.2],records):
        expected=z*np.exp(2j*np.pi*(80*center+7.5*center*center)*orders[:,None])
        error=float(abs(complex_coefficients(row)-expected).max());assert error<2e-11
        errors.append(error)
    base,_,_=curvature(z)
    gauge=z*np.exp(1j*(.71+orders[:,None]*.91));gauged,_,_=curvature(gauge)
    assert np.max(abs(base-gauged))<2e-13
    check=transfer_check(*records)
    assert max(row['future_weighted_phase_chord_error'] for row in check['channels'])<1e-16
    swapped=fit(x[:,::-1],rate,0,times,frequency,.4,settings)
    scaled=fit(x*.31,rate,0,times,frequency,.4,settings)
    assert np.max(abs(complex_coefficients(swapped)-complex_coefficients(records[0])[:,::-1]))<2e-12
    assert np.max(abs(complex_coefficients(scaled)-complex_coefficients(records[0])*.31))<2e-12
    # Wrong-coordinate result is a sensitivity example, not a reference error bar.
    stressed=fit(x,rate,0,times,frequency+.5,.4,settings)
    return dict(analytic_chirp_max_coefficient_errors=errors,exact_phase_gauge_invariance=True,
        channel_swap_and_gain_checked=True,purged_chirp_phase_prediction=check,
        known_coordinate_error_stress_fit_db_lr=stressed['weighted_fit_error_db_lr'],
        scope='Noiseless known harmonic control; 0.5Hz path error is a designed stress, not estimated reference uncertainty.')


def main():
    if OUT.exists():raise SystemExit('Preserve phase_fingerprint_v1; use a new study directory.')
    OUT.mkdir(parents=True)
    control=controls();x,rate,provenance=read_segment('A_exterior_blips','exterior_dynamic_observation')
    origin=provenance['source_seconds'][0];track_path=ROOT/'references/analysis/rev_descent_v1/results.json'
    tracks=json.loads(track_path.read_text());runs={};snapshots={}
    for path_name in ['first_upper_128ms_mean_power','first_upper_192ms_mean_power','second_upper_128ms_mean_power']:
        path=tracks['runs'][path_name];assert path['status']=='connected_peak_path'
        times=np.array([r['seconds'] for r in path['rows']]);frequency=np.array([r['hz'] for r in path['rows']])
        for divisor in [1,5]:
            for window in [.128,.256]:
                settings=PhaseFitSettings(window_seconds=window)
                a=times[0]+window/2+.02;b=times[-1]-window/2-.02
                past=fit(x,rate,origin,times,frequency/divisor,a,settings)
                future=fit(x,rate,origin,times,frequency/divisor,b,settings)
                key=f'{path_name}_div{divisor}_{round(window*1000)}ms'
                if past['status']=='measured' and future['status']=='measured':
                    check=transfer_check(past,future)
                else:check=dict(status='unmeasured',reason='At least one ill-conditioned local fit')
                runs[key]=dict(path_name=path_name,divisor=divisor,settings=settings.__dict__,past=past,future=future,phase_transfer=check)
                print('fitted',key,flush=True)
                if path_name=='first_upper_128ms_mean_power' and divisor==5 and window==.128:
                    snapshots['first_early']=past;snapshots['first_late']=future
                if path_name=='second_upper_128ms_mean_power' and divisor==5 and window==.128:
                    snapshots['second_early']=past
    low,sr,low_provenance=read_segment('A_exterior_low_rev','order_candidates')
    settings=RidgeSettings(window_seconds=.128,hop_seconds=.01,low_hz=30,high_hz=220,anchor_octaves=.15)
    hz,t,power=spectrogram(low,sr,settings);low_paths={}
    for anchor in [52,104]:low_paths[str(anchor)]=follow(hz,t+208,power.mean(axis=1),208.2,210.8,anchor,settings)
    assert all(v['status']=='no_connected_path' for v in low_paths.values())
    exported={}
    for name,row in snapshots.items():
        assert row['status']=='measured'
        z=complex_coefficients(row);common_phase=np.angle(z[:,0])
        variants={'fitted':z,'common_flat':z*np.exp(-1j*common_phase[:,None])}
        files={}
        for variant,coefficients in variants.items():
            files[variant]={}
            for channel,label in enumerate(['L','R']):
                path=OUT/f'{name}_{variant}_{label}.dna';path.write_text(dna_text(row['supplied_root_hz'],coefficients[:,channel]),encoding='utf-8')
                files[variant][label]=dict(file=path.name,sha256=sha(path))
        exported[name]=dict(fit=row,files=files,
            semantics='Two microphone observations, separately fitted. Common phase rearrangement preserves each harmonic amplitude and L/R relative phase. Not physical banks. Static observed root is not engine RPM calibration.')
    fig,axes=plt.subplots(1,2,figsize=(11,4.4),constrained_layout=True)
    for name,row in snapshots.items():
        z=complex_coefficients(row);harmonic=np.arange(1,len(z)+1)
        axes[0].plot(harmonic*row['supplied_root_hz'],20*np.log10(np.maximum(abs(z[:,0]),1e-20)),label=name)
        value,weight,mask=curvature(z);k=np.arange(2,len(z))
        axes[1].plot(k[mask[:,0]],np.angle(value[mask[:,0],0])*180/np.pi,'o',ms=3,label=name)
    axes[0].set(xlabel='Snapshot coordinate frequency / Hz',ylabel='Fitted L amplitude / dBFS',title='Local mixed-recording harmonic coefficients',xlim=(0,8000))
    axes[1].set(xlabel='Supplied-coordinate harmonic index',ylabel='Adjacent phase curvature / degrees',title='Strong triplets only / mixed observation',ylim=(-190,190))
    for ax in axes:ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.savefig(OUT/'phase_fingerprint.png',dpi=160);plt.close(fig)
    result=dict(schema='vsl.phase-fingerprint/1',runtime='0.16.0 unchanged',reference=provenance,controls=control,
        runs=runs,low_reference=dict(provenance=low_provenance,settings=settings.__dict__,anchored_paths=low_paths,
            consequence='No low-rev phase calibration exported from these failed full-interval paths.'),
        snapshots=exported,inputs={track_path.relative_to(ROOT).as_posix():sha(track_path)},
        sources={p.relative_to(ROOT).as_posix():sha(p) for p in [ROOT/'tools/phase_fingerprint.py',ROOT/'tools/analyze_phase_fingerprint.py',ROOT/'tools/ridge_tracks.py',ROOT/'tools/reference_segments.py']},
        files={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file()},
        interpretation='Supplied ridge/divisor coordinates only; unknown engine order, RPM/load, source separation and microphone/room transfer. Local DNA is a reconstruction instrument, not a calibrated V10 bank profile. Purged phase checks condition on the full frequency paths and measured future amplitude weights.')
    (OUT/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(result='pass',snapshots={k:dict(root=v['fit']['supplied_root_hz'],fit_error=v['fit']['weighted_fit_error_db_lr']) for k,v in exported.items()},
        phase_transfer={k:v['phase_transfer'] for k,v in runs.items()}),indent=2))


if __name__=='__main__':main()
