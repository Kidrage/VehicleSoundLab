"""Show the original failed prerequisite and all diagnosed omissions."""
import argparse
import shutil
import sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','diagnostic','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args()
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
diagnostic=load(a.diagnostic/'report.json')
audit=load(a.audit/'report.json')
assert audit['result']=='all12_raw_peak_arithmetic_and_truth_projection_omission_diagnostics_verified'
assert audit['input_report_sha256']==sha(a.input/'report.json')
assert audit['diagnostic_report_sha256']==sha(a.diagnostic/'report.json')
a.out.mkdir(parents=True,exist_ok=False)
shutil.copy2(__file__,a.out/'executed_plot.py')
fig,axes=plt.subplots(2,3,figsize=(15,8),layout='constrained')
for ax,i in zip(axes.flat,[8,9,10,11]):
    data=np.load(a.diagnostic/f'tile_{i:02d}.npz')
    power=data['power'].sum(axis=1)
    hz=np.arange(len(power))*4
    raw=load(a.diagnostic/f'raw_peaks_{i:02d}.json')
    select=(hz>=84)&(hz<=136)
    ax.plot(hz[select],10*np.log10(power[select]),'.-',color='C0',lw=1)
    for peak in raw:
        if 84<=peak['hz']<=136:
            ax.scatter(peak['hz'],10*np.log10(power[peak['bin']]),s=65,
                marker='o' if peak['selected'] else 'x',color='green' if peak['selected'] else 'red')
    near=[v for v in raw if abs(v['hz']-115.7)<=4]
    label=f"116Hz peak prominence {near[0]['prominence_db']:.2f}dB" if near else 'No raw local maximum near 115.7Hz'
    ax.axvline(115.7,color='red',ls='--',lw=.8)
    ax.set_title(f'Window {i} / '+label,fontsize=10)
    ax.set_xlim(84,136)
    ax.set_ylim(-75,-22)
    ax.set_xlabel('Native frequency (Hz)')
    ax.set_ylabel('Combined LR cell power (dBFS)')
    ax.grid(alpha=.2)
ax=axes.flat[4]
tt=(np.arange(12)+.5)*.25
counts=[v['selected_modes'] for v in diagnostic['rows']]
ax.bar(tt,counts,width=.18,color=['C0']*9+['red']*3)
ax.axhline(10,color='black',ls='--',lw=.8,label='10 actual continuous components')
ax.set_ylim(0,11)
ax.set_title('Original candidate count / all 12 windows',fontsize=10)
ax.set_xlabel('Time (s)')
ax.set_ylabel('Selected modes')
ax.legend(fontsize=8)
ax=axes.flat[5]
for key,label,color in [('candidate','Actual cubic fit','C0'),('restricted','Truth basis restricted to detected modes','C1'),('full','Full truth basis / diagnostic only','C2')]:
    values=[]
    for row in diagnostic['rows']:
        value=row['candidate_weighted_relative_residual_LR'][0] if key=='candidate' else row['projections']['full_known_basis' if key=='full' else 'known_basis_for_detected_components']['weighted_relative_residual_LR'][0]
        values.append(value)
    ax.semilogy(tt,values,'.-',lw=1,color=color,label=label)
ax.axvspan(2.25,3,color='red',alpha=.07)
ax.set_xlabel('Time (s)')
ax.set_ylabel('Weighted relative residual, L')
ax.set_title('Representation versus omission / no new estimator',fontsize=10)
ax.grid(alpha=.2)
ax.legend(fontsize=7)
fig.suptitle('Cubic-patch prerequisite FAILED: 115.7Hz component is omitted by original peak selection\n8dB prominence threshold unchanged; green: selected peak, red: rejected/absent; all later controls and real data remain unexecuted',fontsize=11)
fig.savefig(a.out/'omission.png',dpi=150)
plt.close(fig)
save(a.out/'report.json',dict(result='failed_prerequisite_omission_and_truth_only_projection_plotted',
    input_report_sha256=sha(a.input/'report.json'),diagnostic_report_sha256=sha(a.diagnostic/'report.json'),
    audit_report_sha256=sha(a.audit/'report.json'),images={'omission.png':sha(a.out/'omission.png')}))
