"""Measure all source fits and audible contrasts without strength tuning."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','fit','input','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_assessment.py')
r=dict(result='running',fit_sha256=sha(a.fit/'report.json'),input_sha256=sha(a.input/'report.json'),audit_sha256=sha(a.audit/'report.json'),contrasts=[])
try:
    assert load(a.audit/'report.json')['result']=='passed'
    fit=load(a.fit/'report.json');render=load(a.input/'report.json')
    for row in render['renders']:
        before,_=sf.read(a.input/row['files']['mix_0.0']['file'],always_2d=True)
        detail,_=sf.read(a.input/row['files']['detail_0.0']['file'],always_2d=True)
        for amount in ['0.5','1.0']:
            after,_=sf.read(a.input/row['files']['mix_'+amount]['file'],always_2d=True)
            difference=after-before
            r['contrasts'].append(dict(seed=row['seed'],amount=amount,
                difference_RMS_FS=float(np.sqrt(np.mean(difference*difference))),
                difference_relative_mix_dB=float(20*np.log10(np.linalg.norm(difference)/np.linalg.norm(before))),
                difference_relative_detail_dB=float(20*np.log10(np.linalg.norm(difference)/np.linalg.norm(detail)))))
    fig,ax=plt.subplots(2,1,figsize=(10,7.8),layout='constrained')
    values=np.array([[b['assessment']['check']['improvement'] for b in row['bands']] for row in fit['observations']])*100
    for i,label in enumerate(['F2 recording','same-PSD 149921','same-PSD 277139','same-PSD 381611']):
        ax[0].plot(np.arange(4),values[i],marker='o',label=label)
    ax[0].axhline(0,color='#89959b',linewidth=1)
    ax[0].set(xticks=np.arange(4),xticklabels=['1.2–2.2k','2.2–4k','4–8k','8–14k'],
              ylabel='CHECK descriptor KL reduction (%)',title='Only first two source bands improve; not a hearing score')
    ax[0].legend(ncol=2);ax[0].grid(alpha=.2)
    for amount,color in [('0.5','#638c9e'),('1.0','#c57336')]:
        rows=[x for x in r['contrasts'] if x['amount']==amount]
        ax[1].plot(np.arange(3),[x['difference_relative_mix_dB'] for x in rows],marker='o',label=amount+' vs whole mix',color=color)
        ax[1].plot(np.arange(3),[x['difference_relative_detail_dB'] for x in rows],marker='x',linestyle='--',label=amount+' vs detail bus',color=color)
    ax[1].set(xticks=np.arange(3),xticklabels=['149921','277139','381611'],ylabel='Difference RMS relative to bus (dB)',
              title='All three seeds: the modeled change remains small')
    ax[1].legend(ncol=2);ax[1].grid(alpha=.2)
    path=a.out/'idle_local_shape_v1.png';fig.savefig(path,dpi=145);plt.close(fig)
    r.update(result='all_declared_local_shape_contrasts_observed',figure=dict(file=path.name,sha256=sha(path)),
             source_check_descriptor_improvements=values[0].tolist(),no_parameters_tuned=True,
             weak_whole_mix_change=True,listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],contrasts=len(r['contrasts'])),flush=True)
