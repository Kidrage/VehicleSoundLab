"""Publish audited feasibility and slope limits; no audio or listening page."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','audit','out'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    study=load(a.study/'report.json');audit=load(a.audit/'report.json')
    assert study['result']=='six_source_conditional_phase_feasibility_ready'
    assert audit['result']=='independent_conditional_phase_audit_passed'
    assert audit['producer_sha256']==sha(a.study/'report.json')
    a.out.mkdir(parents=True,exist_ok=False)
    dest=a.out/'exact_sources/tools';dest.mkdir(parents=True)
    shutil.copy2(__file__,dest/Path(__file__).name)
    labels=[f'{i+1}/{j+1}' for i in range(6) for j in range(4)]
    rows=[dict(source=i+1,order=h['order'],hz=h['order']*r['root_hz'],
               gap=h['tau'],slope=h['inverse_uniform_slope_bound'])
          for i,r in enumerate(study['cases']) for h in r['harmonics']]
    values=dict(band_labels=labels,errors=study['band_complex_errors'],harmonics=rows,
        meaning='Training coefficient feasibility, not generated audio or a measured engine time law')
    save(a.out/'figure_inputs.json',values)
    plt.rcParams.update({'font.size':10,'axes.titlesize':12})
    fig,axes=plt.subplots(1,2,figsize=(15,5.3),layout='constrained')
    x=np.arange(24)
    for key,label,color,marker in [('parent_pooled','Parent model','#a64b22','o'),
        ('LP_class','Per-harmonic LP solution','#2266a0','x'),
        ('positive_probe','Positive continuity probe','#218b5a','+')]:
        axes[0].plot(x,values['errors'][key],label=label,color=color,marker=marker,lw=.9,ms=5)
    axes[0].set_yscale('log');axes[0].set_xticks(x,labels,rotation=90,fontsize=8)
    axes[0].set(xlabel='Source / band (3-6, 6-8, 8-10, 10-14 kHz)',
                ylabel='Absolute complex coherence error',title='All 24 coordinates; same amplitude energy')
    axes[0].legend(loc='lower left',fontsize=9);axes[0].grid(alpha=.2)
    for inexact,label,color in [(False,'Class target feasible','#2266a0'),(True,'Class target inexact','#a64b22')]:
        selected=[r for r in rows if (r['gap']>2e-7)==inexact]
        axes[1].scatter([r['hz']/1000 for r in selected],[r['slope'] for r in selected],
                        s=8,alpha=.45,label=label,color=color,rasterized=True)
    axes[1].set_yscale('log');axes[1].set(xlabel='Harmonic frequency (kHz)',
        ylabel='Inverse-CDF slope upper bound (rad / unit uniform)',
        title='Positive sparse coupling can still be very steep')
    axes[1].legend(loc='lower right',fontsize=9);axes[1].grid(alpha=.2)
    fig.suptitle('Conditional phase: feasible stereo moments do not establish natural time variation',fontsize=14)
    path=a.out/'conditional_phase_feasibility.png';fig.savefig(path,dpi=150);plt.close(fig)
    save(a.out/'report.json',dict(result='conditional_phase_feasibility_figure_ready',
        sources={'tools/review_conditional_phase_feasibility_v1.py':sha(__file__)},
        inputs={str(a.study/'report.json'):sha(a.study/'report.json'),str(a.audit/'report.json'):sha(a.audit/'report.json')},
        figure_inputs_sha256=sha(a.out/'figure_inputs.json'),images={path.name:sha(path)}))
    print(path)


if __name__=='__main__':main()
