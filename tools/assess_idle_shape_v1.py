"""Observe all new finite waves; report shortcomings without tuning the recipe."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
from idle_cyclic_detail_v1.observer import analytic,covariance
from idle_phase_recipe_v1.phase import spline,phasors
from idle_positive_power_v1.model import predict,average

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(Path(__file__),a.out/'executed_assessment.py')
r=dict(result='running',input_report_sha256=sha(a.input/'report.json'),audit_sha256=sha(a.audit/'report.json'),
    observations=[],source_branch_assessment={})
try:
    assert load(a.audit/'report.json')['result']=='passed'
    report=load(a.input/'report.json');model=load(a.input/'model.json')
    source=report['fits'][0]['model'];cyclic=a.workspace/'baselines/idle_cyclic_detail_v1/evidence/observe1'
    references=[]
    for part in ['train','check']:
        with np.load(cyclic/('source_'+part+'.npz')) as f:references.append(f['covariance'])
        with np.load(a.input/('source_'+part+'.npz')) as f:feature=f['feature'];power=f['power']
        target=average(power)/source['reference_power'];new=average(predict(source,feature))
        common=np.repeat(average(predict(report['law'],feature)),2,axis=1)
        baseline=np.mean((target-common)**2,axis=0);candidate=np.mean((target-new)**2,axis=0)
        r['source_branch_assessment'][part]=dict(common_band_q_mse=baseline.tolist(),separate_branch_q_mse=candidate.tolist(),
            relative_reduction=(1-candidate/baseline).tolist(),interpretation='Branch prediction only; not the normalized generated-shape waveform or hearing.')
    references=np.array(references)
    for row in report['renders']:
        seed=row['seed'];path=a.workspace/f'baselines/idle_phase_recipe_v1/evidence/render2/motion_{seed}.npz'
        with np.load(path) as f:motion=spline(report['phase_model'],f['coordinate_nodes'])
        for amount in [0.,.5,1.]:
            wave=a.input/row['files']['mix_'+str(amount)]['file'];all_audio,rate=sf.read(wave,always_2d=True)
            for block in range(8):
                start=block*144000;audio=all_audio[start:start+144000]
                t=np.arange(start,start+144000)/48000;z=phasors(report['phase_model'],motion,t)
                x,sos=analytic(audio);c,denominator=covariance(x[12000:-12000],z[12000:-12000])
                path=a.out/f'cyclic_{seed}_{amount}_{block}.npz';np.savez_compressed(path,covariance=c)
                distances=np.sqrt(np.mean((abs(references)-abs(c))**2,axis=(1,2,3)))
                by_band=np.sqrt(np.mean((abs(references)-abs(c))**2,axis=(1,3)))
                hz,psd=signal.welch(audio[:,0],48000,nperseg=8192,noverlap=4096)
                power=[float(psd[(hz>=lo)&(hz<hi)].sum()*48000/8192) for lo,hi in [[30,120],[120,400],[400,1200],*model['bands_hz']]]
                observation=dict(seed=seed,amount=amount,block=block,file=path.name,sha256=sha(path),
                    distances_train_check=distances.tolist(),band_distances_train_check=by_band.tolist(),bandpowers=power)
                if amount==0 and block<4:
                    old=cyclic/f'relation_full_{seed}_block{block}.npz'
                    with np.load(old) as f:before=f['covariance']
                    assert np.array_equal(before,c)
                    observation['old_cyclic_curve_exact']=True
                r['observations'].append(observation)
        save(a.out/'report.json',r);print(dict(seed=seed,observations=len(r['observations'])),flush=True)
    r['summaries']={}
    for amount in [0.,.5,1.]:
        group=[v for v in r['observations'] if v['amount']==amount]
        d=np.array([v['distances_train_check'] for v in group])
        r['summaries'][str(amount)]=dict(all24_distances_train_check=d.tolist(),median_train_check=np.median(d,axis=0).tolist())
    fig,axes=plt.subplots(4,2,figsize=(12,12),constrained_layout=True)
    for band in range(4):
        for part in range(2):
            ax=axes[band,part];means=[];low=[];high=[]
            for amount in [0.,.5,1.]:
                values=np.array([v['band_distances_train_check'][part][band] for v in r['observations'] if v['amount']==amount])
                means.append(values.mean());low.append(values.min());high.append(values.max())
            ax.plot([0,.5,1],means,'o-',color='#257b72');ax.fill_between([0,.5,1],low,high,color='#257b72',alpha=.16)
            ax.set_title(f"{model['bands_hz'][band]} Hz | F2 {'TRAIN' if part==0 else 'CHECK'}")
            ax.set_xticks([0,.5,1],['Original','Shape 50%','Shape 100%']);ax.grid(alpha=.2)
            ax.set_ylabel('Cyclic magnitude curve RMS gap')
    fig.suptitle('All 3 seeds × 8 windows: mean and full range, not confidence / hearing scores')
    path=a.out/'cyclic_gap.png';fig.savefig(path,dpi=130);plt.close(fig)
    r['figure']=dict(file=path.name,sha256=sha(path))
    r.update(result='all72_shape_windows_observed_without_tuning',all24seconds_each_observed=True,
        all12prior_cyclic_baseline_curves_exact=True,check_used_for_fit=False,
        waveform_or_profile_changed_after_observation=False,
        limits='Short-time observer distances are descriptive; source branches are filtered mixed audio. No human hearing, long-run or physical-source claim.')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],summaries={k:v['median_train_check'] for k,v in r.get('summaries',{}).items()}),flush=True)
