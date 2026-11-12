"""Compare indicated startup shape with current policy and fixed coarse audio trials."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import sha,read
from drive_evidence_v1.family import follow

a.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.A-startup-indicated-comparison/1',result='running',runtime_changed=False,
       exact_crank_RPM_identified=False,instantaneous_phase_qualified=False,input_sha256={},paths=[])
try:
    annotation=repo/'research/A_startup_video_v2_annotations.json'
    plan=json.loads(annotation.read_text(encoding='utf-8'));trial=plan['audio_family_trial_predeclaration']
    observation=Path(plan['observation']);observed=json.loads(observation.read_text(encoding='utf-8'))
    assert observed['result']=='HD_local_startup_frames_decoded'
    assert sha(observed['source'])==observed['source_sha256']
    by_frame={v['source_frame_index']:v for v in observed['decoded_frames']}
    rows=[]
    for reading in plan['readings']:
        frame=by_frame[reading['source_frame_index']];assert sha(observation.parent/frame['file'])==frame['sha256']
        rows.append(dict(reading,seconds=frame['source_seconds'],file=frame['file'],sha256=frame['sha256']))
    x,meta=read(a.workspace,'A_start_context','audio_onset_observation');r['approved_audio']=meta
    for path in (annotation,observation,repo/'src/profiles/lifecycle.c',
                 a.workspace/'references/analysis/startup_action_v1/audit1/report.json'):
        r['input_sha256'][str(path)]=sha(path)
    old=json.loads((a.workspace/'references/analysis/startup_action_v1/audit1/report.json').read_text(encoding='utf-8'))
    r['old_policy']=old['controller_policy'];r['annotated_readings']=rows
    # Read the actual policy from the frozen audit and bind its unchanged C.
    assert '1150' in (repo/'src/profiles/lifecycle.c').read_text(encoding='utf-8')
    r['indicated_shape']=dict(peak_observed_lower_bound_RPM=max(v['rpm_interval'][0] for v in rows),
        peak_observed_upper_bound_RPM=max(v['rpm_interval'][1] for v in rows),
        old_1150_peak_below_indicated_flare=True,
        interpretation='Instrument-indicated broad shape only; not calibrated crank trace or source phase')
    assert r['indicated_shape']['peak_observed_lower_bound_RPM']>1150
    size=round(trial['window_ms']*.001*48000)
    def spectrum(audio):
        hz,t,z=signal.stft(audio,48000,nperseg=size,noverlap=size-240,axis=0,boundary=None,padded=False)
        return hz,t,np.mean(abs(z)**2,axis=1)
    hz,t,power=spectrum(x);t+=meta['seconds'][0]
    for reference in trial['reference_multiples']:
        path=follow(hz,t,power,*trial['audio_source_seconds'],trial['anchor_root_hz'],
            reference_multiple=reference,check_multiples=trial['check_multiples'],
            max_octaves_per_second=trial['max_octaves_per_second'],root_bounds=trial['root_bounds_hz'])
        r['paths'].append(path)
    if all(v['rows'] for v in r['paths']):
        f=[np.array([v['root_hz'] for v in p['rows']]) for p in r['paths']]
        relative=abs(f[0]-f[1])/(.5*(f[0]+f[1]));quantiles=np.percentile(relative,[50,95,100])
        r['paired_coarse_gate']=dict(relative_quantiles=quantiles.tolist(),passed=bool(quantiles[1]<=.05 and quantiles[2]<=.10))
    else:r['paired_coarse_gate']=dict(passed=False,reason='Missing complete independent coarse family')
    # A known chirp uses imposed analytic phase and independently generated
    # partials. This checks coarse timing/frequency bias, not phase recovery.
    sample=np.arange(3*48000)/48000;root=85-50*np.clip((sample-1)/1.2,0,1)
    phase=2*np.pi*np.cumsum(root)/48000
    known=sum(.01*np.cos(k*phase+.1*k) for k in (2,3,5,7))
    kh,kt,kp=spectrum(np.column_stack((known,known)))
    controls=[]
    for reference in trial['reference_multiples']:
        path=follow(kh,kt,kp,.8,2.4,85,reference_multiple=reference,check_multiples=(2,7),
                    max_octaves_per_second=4,root_bounds=(30,110))
        assert path['rows']
        expected=np.interp([v['seconds'] for v in path['rows']],sample,root)
        measured=np.array([v['root_hz'] for v in path['rows']]);p95=float(np.percentile(abs(measured-expected),95))
        assert p95<1, p95
        controls.append(dict(reference=reference,p95_error_hz=p95))
    r['known_chirp_coarse_controls']=controls
    fig,axes=plt.subplots(3,1,figsize=(11,10),constrained_layout=True)
    times=np.array([v['seconds'] for v in rows]);lo=np.array([v['rpm_interval'][0] for v in rows]);hi=np.array([v['rpm_interval'][1] for v in rows])
    axes[0].errorbar(times,(lo+hi)/2,yerr=(hi-lo)/2,fmt='.',capsize=3,label='HD indicated RPM intervals')
    axes[0].axhline(1150,color='#d25448',ls='--',label='Old controller peak1150RPM')
    axes[0].set(xlim=(36.8,39.5),ylim=(0,2800),ylabel='Indicated RPM',title='A stationary start: picture observation, not ECU telemetry');axes[0].legend()
    axes[1].pcolormesh(t,hz,10*np.log10(np.maximum(power,1e-30)),vmin=-70,vmax=-12,shading='auto')
    axes[1].set(xlim=(37.1,39.8),ylim=(25,800),ylabel='Acoustic Hz',title='Original stereo total;160ms Hann, no phase warp')
    for path in r['paths']:
        if path['rows']:axes[2].plot([v['seconds'] for v in path['rows']],[v['root_hz'] for v in path['rows']],label=f"reference multiple{path['reference_multiple']}")
    axes[2].set(xlim=(37.1,39.8),ylim=(25,110),xlabel='Decoded source seconds; display/audio offset unknown',ylabel='Acoustic root Hz',title='Predeclared85Hz-anchor trial; missing paths stay missing')
    if any(v['rows'] for v in r['paths']):axes[2].legend()
    fig.savefig(a.out/'comparison.png',dpi=140);plt.close(fig)
    sources=[Path(__file__),repo/'tools/drive_evidence_v1/family.py',repo/'tools/drive_evidence_v1/sources.py',annotation]
    r['source_sha256']={str(path.relative_to(repo)).replace('\\','/'):sha(path) for path in sources}
    for path in sources:
        target=a.out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    r.update(result='indicated_shape_observed_and_coarse_family_tested',plot_sha256=sha(a.out/'comparison.png'),
        limits=plan['cautions']+['No source model compilation or new startup/controller settings',
        'No instantaneous phase, physical engine order or A/V calibration inferred from a coarse path'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],shape=r['indicated_shape'],coarse_gate=r['paired_coarse_gate'],paths=[{k:v for k,v in z.items() if k!='rows'} for z in r['paths']])) )
