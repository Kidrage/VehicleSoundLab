"""Inspect the delivered crank representation; no fit, new preset or audition."""
import argparse,hashlib,json
from copy import deepcopy
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy import signal
from startup_character_v1.expression import ExpressionStarter
from render_startup_expression_v1 import controls,voice

RATE=48000
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def power(x):return float(np.mean(np.asarray(x,dtype=float)**2))
def band_fractions(x):
    f,p=signal.welch(x,fs=RATE,nperseg=2048,noverlap=1024,axis=0)
    edges=[0,60,300,1200,4500,14000,24001]
    values=np.array([np.sum(p[(f>=lo)&(f<hi)]) for lo,hi in zip(edges[:-1],edges[1:])])
    return (values/values.sum()).tolist()


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];base=Path('E:/VehicleSoundLab/references/analysis')
    listen=base/'startup_expression_v1/listen2';recipe=json.loads((listen/'recipe.json').read_text())
    profile=json.loads((listen/'model/crank/profile.json').read_text());library=listen/'startup_character_bridge.dll'
    model=deepcopy(profile);model['variation']=model['ridge_variation']=0.
    old=np.load(base/'startup_rhythm_v1/author1/decomposition.npz')
    source=old['source'];source_core=old['core'];source_residual=old['remainder'];frames=len(source)
    with sf.SoundFile(profile['source']) as f:
        f.seek(round(47.6*RATE));raw=f.read(frames,dtype='float64')
    assert np.array_equal(raw,source)
    assert sha(Path(profile['source']))==profile['source_sha256']
    assert len(profile['ridges'])==40 and frames==27840
    def nominal(length,core,texture):
        v=ExpressionStarter(library,model,97346)
        try:return v.expression(np.arange(length)/length,np.ones(length,dtype=int),1.,1.,core,texture)
        finally:v.close()
    same_core=nominal(frames,1.,0.)
    gate=1-np.exp(-(np.arange(frames)+1)/384.)
    phase_error=float(np.max(abs(same_core-source_core*gate[:,None])))
    assert phase_error<2e-7,phase_error
    # Delivered full-time controls include the pre-roll RNG advancement. Read
    # the exact saved recipe, seed and library rather than re-authoring a voice.
    data,_,sections,_=controls(recipe,round(recipe['seconds']*RATE));cfg=data['crank']
    c=deepcopy(cfg);c['texture']=0.;tonal=voice(library,profile,97346,c,479)*cfg['weight'][:,None]
    c=deepcopy(cfg);c['core']=0.;texture=voice(library,profile,97346,c,479)*cfg['weight'][:,None]
    saved,_=sf.read(listen/'crank.wav',always_2d=True,dtype='float64')
    sum_error=float(np.max(abs(tonal+texture-saved)));assert sum_error<3e-8,sum_error
    lo,hi=sections['crank'];active=slice(round(lo*RATE),round(hi*RATE))
    t=tonal[active];r=texture[active];m=saved[active]
    pm=power(m);cross=float(2*np.mean(t*r));assert abs(power(t)+power(r)+cross-pm)<1e-9
    n_stretch=round(recipe['crank_seconds']*RATE);stretched=nominal(n_stretch,1.,0.)
    lengths=sorted({row['frames'] for row in profile['ridges']})
    stretch=n_stretch/frames
    # Phase at the midpoint of actual overlapping, close-frequency atoms.
    # Under constant pitch1, a time stretch scales the phase integral while
    # retaining fitted initial phase. This is representational sensitivity,
    # not evidence assigning a pair to the same physical component.
    phase_changes=[]
    rows=profile['ridges']
    for i,x in enumerate(rows):
        for y in rows[i+1:]:
            left=max(x['start_frame'],y['start_frame']);right=min(x['start_frame']+x['frames'],y['start_frame']+y['frames'])
            if right-left<1024:continue
            pos=(left+right)/2;tx=(pos-x['start_frame'])/RATE;ty=(pos-y['start_frame'])/RATE
            hx=x['hz']+x['slew_hz_per_second']*tx;hy=y['hz']+y['slew_hz_per_second']*ty
            if abs(hx-hy)>40:continue
            ix=2*np.pi*(x['hz']*tx+.5*x['slew_hz_per_second']*tx*tx)
            iy=2*np.pi*(y['hz']*ty+.5*y['slew_hz_per_second']*ty*ty)
            angle=np.angle(np.exp(1j*(stretch-1)*(ix-iy)))
            phase_changes.append(abs(float(angle))*180/np.pi)
    coarse=profile['envelope']
    report=dict(schema='vsl.startup-crank-diagnosis/1',status='diagnostic_only',
        source_seconds=profile['seconds'],source_sha256=profile['source_sha256'],native_sha256=sha(library),
        source_duration=frames/RATE,delivered_duration=n_stretch/RATE,time_stretch=stretch,
        source_atom_duration_ms=[x/RATE*1000 for x in lengths],output_atom_duration_ms=[x/RATE*1000*stretch for x in lengths],
        coarse_envelope_knots=len(coarse),source_coarse_interval_ms=frames/RATE/8*1000,output_coarse_interval_ms=n_stretch/RATE/8*1000,
        spectral_states=len(profile['profiles']),source_stage_span_ms=frames/RATE/3*1000,output_stage_span_ms=n_stretch/RATE/3*1000,
        native_matches_original_projection_phase_at_original_timing=phase_error,
        delivered_stem_decomposition_error=sum_error,
        normalized_source_projection_explained=1-float(np.sum((source_residual/old['contour'][:,None])**2)/np.sum((source/old['contour'][:,None])**2)),
        delivered_procedural_power_ratio={'OSC':power(t)/pm,'random_texture':power(r)/pm,'signed_cross':cross/pm},
        power_ratio_meaning='Actual C contributions in delivered crank only, not real motor/noise fractions or a hearing score',
        source_band_fractions=band_fractions(source),candidate_band_fractions=band_fractions(m),
        bands_hz=[0,60,300,1200,4500,14000,24000],
        same_representation_core_power_source=power(same_core),same_representation_core_power_stretched=power(stretched),
        overlap_close_frequency_atom_pair_count=len(phase_changes),
        overlapping_pair_phase_change_median_degrees=float(np.median(phase_changes)) if phase_changes else None,
        overlapping_pair_phase_change_max_degrees=float(max(phase_changes)) if phase_changes else None,
        phase_change_limits='Continuous midpoint phase-integral diagnostic with pitch1, excluding jitter/gate/entry-sample discretization; not physical shaft identification',
        code_facts={'pitch_not_driven_by_crank_RPM':True,'per_atom_initial_phase_and_detune':True,
                    'residual_preserves_three_PSD_shapes_not_source_time_phase':True,'common_roughness_tau_seconds':.012},
        inference='Time and carrier controls are decoupled; fitted overlap relations change under stretch. Remaining mechanical structure may be randomized by the PSD residual representation.',
        no_new_fit=True,no_DSP_or_App_change=True,no_new_listening_candidate=True)
    (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    np.savez(a.output/'diagnostic_components.npz',source=source,source_core=source_core,source_residual=source_residual,
        output_core=t,output_texture=r,output_sum=m)
    shutil_source=Path(__file__);(a.output/'executed_diagnosis.py').write_bytes(shutil_source.read_bytes())
    print(json.dumps({k:report[k] for k in ('time_stretch','output_atom_duration_ms','normalized_source_projection_explained','delivered_procedural_power_ratio','overlap_close_frequency_atom_pair_count','overlapping_pair_phase_change_median_degrees','overlapping_pair_phase_change_max_degrees','native_matches_original_projection_phase_at_original_timing','delivered_stem_decomposition_error','source_band_fractions','candidate_band_fractions')}),flush=True)
if __name__=='__main__':main()
