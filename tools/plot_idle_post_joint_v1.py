"""Show all latent constraints and every leave-group check; no invalid sound preview."""
import argparse
import shutil
import sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import SymLogNorm
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_plot.py')
r=load(a.input/'report.json');audit=load(a.audit/'report.json')
assert audit['result']=='all2048_full_tensor_operators_and_both64group_feasibilities_verified'
assert audit['input_report_sha256']==sha(a.input/'report.json')
fig,axes=plt.subplots(2,2,figsize=(13,10),layout='constrained')
labels=['1.2-2.2','2.2-4','4-8','8-14'];colors=['#267f8d','#b76b46'];names=['variance_factors','compound_sign_groups']
summary=[]
for index,name in enumerate(names):
    row=r['families'][name];solution=row['solution'];latent=np.asarray(solution['latent'])
    normalized=latent/np.sqrt(np.outer(np.diag(latent),np.diag(latent)))
    ax=axes[0,index]
    im=ax.imshow(normalized,cmap='RdBu_r',norm=SymLogNorm(linthresh=1,vmin=-140,vmax=140))
    for b in range(4):
        for c in range(4):ax.text(c,b,f'{normalized[b,c]:.2f}',ha='center',va='center',color='white' if abs(normalized[b,c])>10 else 'black')
    ax.set(title=name+'\nRequired normalized latent entries; |entry| <= 1 necessary',xticks=range(4),yticks=range(4),
           xticklabels=labels,yticklabels=labels,xlabel='Input branch (kHz)',ylabel='Input branch (kHz)')
    fig.colorbar(im,ax=ax,shrink=.8)
    eigen=np.asarray(solution['eigenvalues']);x=np.arange(4)+(index-.5)*.18
    axes[1,0].plot(x,eigen,'o-',color=colors[index],label=name)
    leave=np.array([z['eigenvalues'][0] for z in row['leave_groups']])
    axes[1,1].plot(np.arange(64),leave,'.-',color=colors[index],lw=.7,label=name)
    axes[1,1].axhline(eigen[0],color=colors[index],ls=':',lw=1)
    summary.append(dict(family=name,status=solution['status'],maximum_abs_normalized_latent=float(abs(normalized).max()),
                        all64_indefinite=all(z['status']=='latent_indefinite_REJECTED' for z in row['leave_groups'])))
axes[1,0].axhline(0,color='black',lw=.8);axes[1,0].set(title='All four latent eigenvalues (negative is inadmissible)',
    xticks=range(4),xticklabels=['Minimum','2','3','Maximum'],ylabel='Latent-matrix eigenvalue')
axes[1,0].legend(fontsize=8);axes[1,0].grid(alpha=.2)
axes[1,1].set(title='All 64 leave-group minimum eigenvalues',xlabel='Omitted time-sampling group',ylabel='Minimum latent eigenvalue')
axes[1,1].legend(fontsize=8);axes[1,1].grid(alpha=.2)
fig.suptitle('Actual POST joint budget: BOTH declared white-innovation families rejected\nSampled zero-lag budget only; not a source-level impossibility or a listening result',fontsize=14)
image=a.out/'joint_feasibility.png';fig.savefig(image,dpi=150);plt.close(fig)
save(a.out/'report.json',dict(result='both_latent_matrices_all_eigenvalues_all64groups_plotted',
    input_report_sha256=sha(a.input/'report.json'),audit_sha256=sha(a.audit/'report.json'),
    images=[dict(file=image.name,sha256=sha(image))],families=summary))
print(summary)
