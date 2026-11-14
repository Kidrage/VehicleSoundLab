"""Actual new finite buses through the frozen three-aperture observer and MIX phase estimator."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','render','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha
from idle_short_budget_v1.observe import observe
from idle_short_budget_v1.spectral import project,summarize as spectral
from idle_variation_budget_v1.variation import summarize,budget
from idle_conditioned_detail_v1.features import phases
from idle_phase_recipe_v1.phase import spline,phasors

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},inputs={},cases=[],spectra=[])


def track(path):r['inputs'][str(path)]=sha(path);return path
def checkpoint():save(a.out/'report.json',r)


try:
    names=['tools/observe_idle_complex75_v1.py','tools/idle_short_budget_v1/observe.py','tools/idle_short_budget_v1/spectral.py',
        'tools/idle_variation_budget_v1/variation.py','tools/idle_window_transfer_v1/observe.py',
        'tools/idle_conditioned_detail_v1/features.py','tools/idle_phase_recipe_v1/phase.py','tools/research_archive_v1.py']
    for name in names:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    assert load(track(a.audit/'report.json'))['result']=='passed'
    render=load(track(a.render/'report.json'));root=a.workspace/'baselines'
    # Reuse all previously independently checked source and baseline observations by path/hash.
    parent=root/'idle_short_budget_v1/evidence/observe1';before=load(track(parent/'report.json'))
    r['reuse']=dict(root=str(parent),report_sha256=sha(parent/'report.json'),cases=before['cases'],spectra=before['spectra'],
        audit_sha256=sha(track(root/'idle_short_budget_v1/evidence/audit1/report.json')))
    freq=np.array(load(track(root/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json'))['modal']['frequencies_hz'])
    reference=np.array(load(track(root/'idle_local_partition_v1/evidence/compile2/model.json'))['main_amplitude_LR'])[:,0]
    phase_root=root/'idle_phase_recipe_v1/evidence/render2';model=load(track(phase_root/'model.json'))
    for row in render['renders']:
        seed=row['seed']
        with np.load(track(phase_root/f'motion_{seed}.npz')) as f:motion=spline(model,f['coordinate_nodes'])
        for branch in ['independent_old','complex75']:
            waves={}
            for bus in ['mix','main']:
                entry=row['files'][branch+'_'+bus];path=track(a.render/entry['file']);assert sha(path)==entry['sha256']
                waves[bus],rate=sf.read(path,always_2d=True);assert rate==48000
            for block,start in enumerate(range(0,1152000,144000)):
                mix=waves['mix'][start:start+144000,0];main=waves['main'][start:start+144000,0]
                buses=np.column_stack((mix,main,mix-main));z0=phasors(model,motion,np.arange(start,start+144000)/48000)
                for basis,z in [('procedural',z0),('measured_acoustic',phases(mix,freq[[1,2,4]]))]:
                    label=f'{branch}_{seed}_{block}_{basis}';meta=dict(kind='generated',condition=branch,seed=seed,block=block,first_frame=start,phase_basis=basis)
                    for ms in [50,100,200]:
                        c,condition=observe(buses,freq,z,ms);s=summarize(c[:,0,[1,2,4]],reference);b=budget(c[:,:,[1,2,4]],reference)
                        identity=float(abs(c[:,0]-c[:,1]-c[:,2]).max());assert identity<1e-10
                        file=a.out/f'{label}_{ms}.npz';np.savez_compressed(file,coefficients=c,reference=reference,condition=condition,**s,**b)
                        r['cases'].append(dict(label=label,metadata=meta,window_ms=ms,file=file.name,sha256=sha(file),std=s['std'].tolist(),
                            main_std=b['main_std'].tolist(),detail_std=b['detail_std'].tolist(),lag0_signed_variance_ratios=b['lag0_signed_variance_ratios'].tolist()))
                    residual,beta=project(buses,freq,z);s=spectral(buses,residual,z);file=a.out/f'{label}_spectral.npz'
                    np.savez_compressed(file,beta=beta,**s);r['spectra'].append(dict(label=label,metadata=meta,file=file.name,sha256=sha(file),summary={k:v.tolist() for k,v in s.items()}))
                checkpoint()
            print(dict(seed=seed,branch=branch,blocks=8,phase_bases=2,apertures=3),flush=True)
    assert len(r['cases'])==288 and len(r['spectra'])==96
    r.update(result='complete_actual_complex75_three_aperture_observation',baseline_cases_hash_reused=144,source_cases_hash_reused=24,
        baseline_spectra_hash_reused=48,source_spectra_hash_reused=8,source_physical_separation=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:checkpoint()
print(dict(result=r['result'],cases=len(r['cases']),spectra=len(r['spectra'])),flush=True)
