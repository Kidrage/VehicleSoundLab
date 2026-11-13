"""Both rejected latent matrices and every eigenvalue, without hiding failures."""
import argparse,shutil,sys
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:
    p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha

audit=load(a.audit/'report.json')
assert audit['result']=='both_budget_families_known_controls_tensor_maps_and_certificates_verified'
assert audit['input_report_sha256']==sha(a.input/'report.json')
r=load(a.input/'report.json');a.out.mkdir(parents=True,exist_ok=False)
shutil.copy2(__file__,a.out/'executed_plot.py')
families=list(r['families']);names=['Gaussian variance factors','Compound signed groups']
limit=max(abs(np.array(v['solution']['latent'])).max() for v in r['families'].values())
fig,axes=plt.subplots(1,3,figsize=(15,5),layout='constrained')
for j,(family,name) in enumerate(zip(families,names)):
    solution=r['families'][family]['solution'];matrix=np.array(solution['latent'])
    im=axes[j].imshow(matrix,vmin=-limit,vmax=limit,cmap='coolwarm')
    for b in range(4):
        for c in range(4):axes[j].text(c,b,f'{matrix[b,c]:.1f}',ha='center',va='center',fontsize=9)
    axes[j].set(title=name+'\nExact inverse rejected: indefinite',xlabel='High innovation input',ylabel='High innovation input')
    axes[j].set_xticks(range(4),[2,3,4,5]);axes[j].set_yticks(range(4),[2,3,4,5])
    axes[2].plot(range(4),solution['eigenvalues'],'o-',label=name)
fig.colorbar(im,ax=axes[:2],shrink=.65,label='Algebraic latent moment entry; not a source profile')
axes[2].axhline(0,color='black',ls='--',lw=1)
axes[2].set(title='Every eigenvalue\nPositive-factor models require nonnegative values',xlabel='Sorted eigenvalue index',ylabel='Latent eigenvalue')
axes[2].set_xticks(range(4));axes[2].grid(alpha=.2);axes[2].legend(fontsize=8)
fig.suptitle('Fixed F2 moment budget: both declared white joint-input families fail exact feasibility\nNo eigenvalue projection, fitted rate, new audio or timbre acceptance',fontsize=12)
path=a.out/'idle_joint_budget_rejections.png';fig.savefig(path,dpi=150);plt.close(fig)
save(a.out/'report.json',dict(result='both_rejected_matrices_and_all_eigenvalues_plotted',
    input_report_sha256=sha(a.input/'report.json'),audit_sha256=sha(a.audit/'report.json'),image_sha256=sha(path)))
