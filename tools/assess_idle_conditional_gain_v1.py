"""Plot audited native conditional means, explicitly retaining source rejection."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','diagnosis','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_assessment.py')
run=load(a.input/'report.json');diag=load(a.diagnosis/'report.json');audit=load(a.audit/'report.json')
assert audit['result']=='passed' and audit['input_sha256']==sha(a.input/'report.json')
assert audit['diagnosis_sha256']==sha(a.diagnosis/'report.json') and not run['models']['source']['conditional']['available']
rows=[v for v in diag['cases']+run['evaluations'] if v['part']=='check']
families=['source','phase_149921','phase_277139','phase_381611']
rows=sorted(rows,key=lambda row:families.index(row['family']))
fig,axes=plt.subplots(2,2,figsize=(14,8.3),layout='constrained')
colors=['#087f8c','#d47b19'];x=np.arange(4)
for m,hz in enumerate([75,112]):
    y=np.array([row['fractional_complex_MSE_reduction'][m] for row in rows])*100
    axes[0,0].bar(x+(m-.5)*.30,y,width=.30,label=f'{hz} Hz',color=colors[m])
axes[0,0].axhline(0,color='black',linewidth=.7)
axes[0,0].set_xticks(x,['F2 source*','PSD control 1','PSD control 2','PSD control 3'])
axes[0,0].set_ylabel('CHECK complex MSE reduction (%)')
axes[0,0].set_title('Source/control transfer; *source fit rejected at 3 bounds')
axes[0,0].legend()
with np.load(a.diagnosis/'source_check.npz') as f:
    t=(np.arange(116)*960+12000+4800)/48000
    for m,ax in enumerate([axes[0,1],axes[1,0]]):
        ax.plot(t,np.abs(f['target'][:,m]),label='Recording observation',color='#252525',linewidth=1.3)
        ax.plot(t,np.abs(f['constant_prediction'][:,m]),label='Constant mean',color='#8e8e8e',linestyle='--')
        ax.plot(t,np.abs(f['conditional_prediction'][:,m]),label='Rejected conditional mean',color=colors[m])
        ax.set_title(f'F2 CHECK ~{[75,112][m]} Hz: much variation remains')
        ax.set_xlabel('Seconds within 3 s portion');ax.set_ylabel('Complex coefficient magnitude (FS)')
        ax.legend(fontsize=8)
check=diag['cases'][1]
base=np.array(check['metrics']['constant']['complex_error_variance'])
new=np.array(check['metrics']['conditional']['complex_error_variance'])
var_reduction=(1-new/base)*100
axes[1,1].bar([0,1],var_reduction[:2],color=colors)
axes[1,1].set_xticks([0,1],['75 Hz','112 Hz']);axes[1,1].set_ylim(0,30)
axes[1,1].set_ylabel('CHECK error variance reduction (%)')
axes[1,1].set_title('Descriptive variance result, not a timbre score')
axes[1,1].text(.03,.94,'Unavailable model; fixed-parameter diagnosis only\nUnknown innovation covariance NOT recovered\n187 Hz gain fixed; no new voice, WAV audition or C',
    transform=axes[1,1].transAxes,va='top',fontsize=9)
for ax in axes.flat:ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
fig.suptitle('Native positive conditional mean through the original OSC observer',fontsize=15)
path=a.out/'evidence.png';fig.savefig(path,dpi=150);plt.close(fig)
r=dict(result='rejected_source_conditional_mean_assessed',input_sha256=sha(a.input/'report.json'),
    diagnosis_sha256=sha(a.diagnosis/'report.json'),audit_sha256=sha(a.audit/'report.json'),
    source_CHECK_complex_MSE_reduction=check['fractional_complex_MSE_reduction'],
    source_CHECK_complex_error_variance_reduction=(var_reduction/100).tolist(),
    source_rejected_active_slopes=3,hidden_innovation_covariance_identified=False,
    known_parameter_error=run['known']['parameter_error'],known_Jacobian_condition=run['known']['conditional']['condition'],
    figure=dict(file=path.name,sha256=sha(path)),listening_improvement_claimed=False,new_voice_or_audition=False)
save(a.out/'report.json',r);print(r)
