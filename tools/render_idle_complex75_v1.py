"""One source-derived joint75candidate and independent-old75control, frozen remainder."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','model','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha
from idle_complex75_v1.model import nodes,table,native,gain
from idle_phase_amplitude_v1.model import nodes as old_nodes,interpolation as old_table,native as old_native,gains as old_gain
from idle_phase_recipe_v1.phase import spline,phasors

INDEPENDENT_OLD_KEY=0x7C75B41D93
a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},inputs={},renders=[])


def track(path):r['inputs'][str(path)]=sha(path);return path
def checkpoint():save(a.out/'report.json',r)


try:
    names=['tools/render_idle_complex75_v1.py','tools/idle_complex75_v1/model.py',
        'tools/idle_phase_amplitude_v1/model.py','tools/idle_phase_recipe_v1/phase.py','tools/research_archive_v1.py','research/idle_complex75_v1_plan.json']
    for name in names:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    fit=load(track(a.model/'report.json'));assert fit['result']=='source_native_complex75_fitted_pending_audit'
    model=load(track(a.model/'model.json'));assert sha(a.model/'model.json')==fit['model_sha256'];compiled=table(model)
    root=a.workspace/'baselines';am=load(track(root/'idle_phase_amplitude_v1/evidence/render2/model.json'));amtable=old_table(am)
    baseline=root/'idle_local_partition_v1/evidence/render1';before=load(track(baseline/'report.json'))
    amp=np.array(load(track(root/'idle_local_partition_v1/evidence/compile2/model.json'))['main_amplitude_LR'])[0]
    profile=load(track(root/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json'))
    delta=np.diff(np.array(profile['modal']['initial_phase_LR'])[1])[0]
    phase_root=root/'idle_phase_recipe_v1/evidence/render2';phase_model=load(track(phase_root/'model.json'))
    C=compiled['covariance'];r['theory']=dict(E_gain_power=1.,E_gain=float(np.exp(-.5*np.trace(C))),
        coherent_power_fraction=float(np.exp(-np.trace(C))),sideband_power_fraction=float(1-np.exp(-np.trace(C))),
        covariance=C.tolist(),fixed75amplitude_LR=amp.tolist(),not_finite_take_RMS=True)
    frames=1152000
    for row in before['renders']:
        seed=row['seed'];base={};original_files={}
        for bus in ['mix','main']:
            entry=row['files'][bus+'_1.0'];file=track(baseline/entry['file']);assert sha(file)==entry['sha256']
            wave,rate=sf.read(file,always_2d=True);assert rate==48000 and len(wave)==frames;base[bus]=wave
            original_files[bus]=dict(file=str(file),sha256=sha(file))
        with np.load(track(baseline/row['nodes_file'])) as f:original_nodes=f['nodes']
        independent=old_nodes(am,seed^INDEPENDENT_OLD_KEY,24);values,white=nodes(model,seed,24)
        with np.load(track(phase_root/f'motion_{seed}.npz')) as f:motion=spline(phase_model,f['coordinate_nodes'])
        deltas={key:np.empty((frames,2)) for key in ['independent_old','complex75']};drivers=np.empty((frames,4));maximum_gain=0.
        for first in range(0,frames,24000):
            count=min(24000,frames-first);time=np.arange(first,first+count)/48000;z=phasors(phase_model,motion,time)[:,0]
            original=old_gain(old_native(original_nodes,amtable,first,count),1.,amtable['covariance'])[:,0]
            old=old_gain(old_native(independent,amtable,first,count),1.,amtable['covariance'])[:,0]
            x=native(values,compiled,first,count);g=gain(x,C);maximum_gain=max(maximum_gain,float(abs(g).max()))
            drivers[first:first+count]=np.column_stack((original,old,g.real,g.imag))
            for c in range(2):
                carrier=z*np.exp(1j*delta*c);before75=amp[c]*carrier.real*original
                deltas['independent_old'][first:first+count,c]=amp[c]*carrier.real*old-before75
                deltas['complex75'][first:first+count,c]=amp[c]*(carrier*g).real-before75
        trace=a.out/f'driver_{seed}.npz';np.savez_compressed(trace,complex_nodes=values,complex_white=white,
            independent_old_nodes=independent,drivers=drivers)
        files={}
        for branch in ['independent_old','complex75']:
            for bus in ['mix','main']:
                wave=base[bus]+deltas[branch];peak=float(abs(wave).max());assert np.isfinite(wave).all() and peak<.85
                file=a.out/f'{branch}_{bus}_{seed}.wav';sf.write(file,wave,48000,subtype='FLOAT')
                files[branch+'_'+bus]=dict(file=file.name,sha256=sha(file),peak=peak,rms=float(np.sqrt(np.mean(wave**2))))
        r['renders'].append(dict(seed=seed,files=files,baseline=original_files,driver_file=trace.name,driver_sha256=sha(trace),
            maximum_complex_gain=maximum_gain,old75_otherAM_coupling_omitted_in_both_branches=True))
        checkpoint();print(dict(seed=seed,files=files),flush=True)
    r.update(result='finite_complex75_candidate_pending_audit',new_candidate_count=1,independent_old_control=True,
        original_source_recording_used_in_synthesis=False,old75_gain_replaced=True,other12_and_detail_recipe_unchanged=True,
        runtime_changed=False,listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:checkpoint()
print(dict(result=r['result'],theory=r['theory']),flush=True)
