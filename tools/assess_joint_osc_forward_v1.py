"""Known-control evidence figure; no naturalness or real-engine recovery score."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_assessment.py')
r=dict(result='running')
try:
    source=load(a.input/'report.json');audit=load(a.audit/'report.json');assert audit['result']=='passed'
    r.update(input_sha256=sha(a.input/'report.json'),audit_sha256=sha(a.audit/'report.json'))
    spec=load(a.input/'spec.json');amplitude=np.array(spec['amplitude'])[[1,2,4]]
    row=next(v for v in source['cases'] if v['kind']=='joint_AM' and v['seed']==149921)
    with np.load(a.input/row['file']) as f:
        target=abs(f['train_true_coefficients'][:,[1,2,4]])
        naive_log=amplitude*f['train_exp_Hann_mean_loggain'];naive_gain=amplitude*f['train_Hann_mean_gain']
        error_log=np.max(abs(target/naive_log-1),axis=0);error_gain=np.max(abs(target/naive_gain-1),axis=0)
    r['first_seed_joint_TRAIN_naive_relative_errors']=dict(exp_mean_log=error_log.tolist(),mean_gain=error_gain.tolist())
    r['known_parameter_recovery']=source['fit']
    r['realized_power_ratio_range']=[min(v['realized_over_expected'] for v in source['power']),max(v['realized_over_expected'] for v in source['power'])]
    r['maximum_predicted_CHECK_window_log_error']=max(v['maximum_window_log_error'] for v in source['predictions'] if not v['used_for_fit'])
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    trace=np.array([v['parameters'] for v in source['fit']['trace']])
    for j,color in enumerate(['#28776c','#d49b3e']):
        axes[0,0].plot(np.arange(len(trace)),trace[:,j],'o-',color=color,label=['75Hz coupling','112Hz coupling'][j])
        axes[0,0].axhline(source['fit']['truth'][j],color=color,linestyle='--',linewidth=.8)
    axes[0,0].set(title='Known2parameters recovered; latent inputs supplied',xlabel='solver evaluation',ylabel='coupling parameter');axes[0,0].legend(fontsize=8)
    axes[0,1].bar(np.arange(3)-.17,error_log*100,.34,label='exp(mean log gain)',color='#d49b3e')
    axes[0,1].bar(np.arange(3)+.17,error_gain*100,.34,label='mean gain',color='#28776c')
    axes[0,1].set_xticks(range(3),['75Hz','112Hz','187Hz'])
    axes[0,1].set(title='Naive window estimates versus actual projection',ylabel='maximum relative magnitude error (%)');axes[0,1].legend(fontsize=8)
    for kind,color in [('phase_only','#8798a4'),('independent_AM','#d49b3e'),('joint_AM','#28776c')]:
        values=[v['realized_over_expected'] for v in source['power'] if '_'+kind+'_' in v['case']]
        axes[1,0].plot(np.arange(len(values)),values,'o-',color=color,label=kind)
    axes[1,0].axhline(1,color='#475563',linestyle='--',linewidth=.8)
    axes[1,0].set(title='Finite realized power differs from ensemble expectation',xlabel='3seeds x2portions',ylabel='realized / analytic expectation');axes[1,0].legend(fontsize=8)
    values=[v for v in source['predictions'] if not v['used_for_fit']]
    axes[1,1].semilogy(np.arange(len(values)),[max(v['maximum_window_log_error'],1e-16) for v in values],'o-',color='#28776c')
    axes[1,1].set_xticks(range(len(values)),[str(v['seed'])+'\n'+v['part'] for v in values],fontsize=8)
    axes[1,1].set(title='Known-input predictions after fitting first3s only',ylabel='max window log magnitude error')
    for ax in axes.flat:ax.grid(alpha=.2)
    fig.suptitle('Joint OSC forward/inverse controls: implementation evidence, not a source voice',fontsize=13)
    path=a.out/'evidence.png';fig.savefig(path,dpi=150);plt.close(fig)
    r.update(result='known_joint_forward_evidence_assessed',figure=dict(file=path.name,sha256=sha(path)),
        measured_noAM_original_gates_passed=source['measured_no_AM_gates_passed'],
        source_model_or_runtime_changed=False,listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],naive_errors=r['first_seed_joint_TRAIN_naive_relative_errors'],
    realized_power_ratio=r['realized_power_ratio_range'],check_error=r['maximum_predicted_CHECK_window_log_error']),flush=True)
