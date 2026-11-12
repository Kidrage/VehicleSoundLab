"""Plot the known-phase representation diagnosis without new estimation."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--diagnosis',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.joint-noise-budget-plot/1',result='running',real_audio_read=False,
    real_source_permitted=False,qualification_changed=False,nonlinear_estimator_rerun=False,sources={})
try:
    parent=json.loads((args.diagnosis/'report.json').read_text(encoding='utf-8'))
    assert parent['result']=='diagnosed_known_noise_and_representation_no_qualification'
    assert parent['higher_order_representation_diagnostic']['actual_estimator_run'] is False
    for relative,digest in parent['sources'].items():
        assert sha(repo/relative)==sha(args.diagnosis/'exact_sources'/relative)==digest
    target=args.out/'exact_sources/tools'/Path(__file__).name
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(__file__,target)
    report['sources'][Path(__file__).resolve().relative_to(repo).as_posix()]=sha(Path(__file__))
    data=np.load(args.diagnosis/'diagnostic_arrays.npz')
    time=data['time']
    interior=(time>=5)&(time<35)
    fig,axes=plt.subplots(1,2,figsize=(11.5,4.3))
    for key,label in (('best_L2_phase_approximation','Cubic'),('quintic_known_phase_approximation','Quintic')):
        error=data[key]-data['true_phase']
        error-=np.median(error[interior])
        axes[0].plot(time[interior],error[interior],label=label)
    gate=parent['common_phase_representation']['original_phase_gate']
    for sign in (-1,1):
        axes[0].axhline(sign*gate,color='black',linestyle='--',linewidth=.6)
    axes[0].set(xlabel='Coarse-cycle coordinate',ylabel='Known-phase approximation error (cycles)',
        title='Known phase: cubic vs quintic, same knot spacing')
    axes[0].legend()
    norms=parent['projection_norms']
    labels=['Known noise','Cubic phase error','Quintic phase error','Exact phase +\namplitude approximation']
    values=[norms['noise'],norms['cubic_phase_approximation_increment'],
        norms['same_spacing_quintic_increment'],norms['exact_known_phase_amplitude_vs_clean']]
    axes[1].barh(labels,values,color=['#777777','#d05a37','#3b8c72','#5285bd'])
    axes[1].invert_yaxis()
    axes[1].set(xlabel='Real finite-window projection error norm',title='Projected error budgets')
    for i,value in enumerate(values):
        axes[1].text(value+max(values)*.015,i,f'{value:.3g}',va='center',fontsize=8)
    axes[1].set_xlim(0,max(values)*1.23)
    fig.suptitle('Analytic diagnosis only; no estimator or timbre qualification',fontsize=11)
    fig.tight_layout(rect=(0,0,1,.94))
    fig.savefig(args.out/'phase_representation.png',dpi=150)
    plt.close(fig)
    report.update(result='plotted_known_representation_diagnosis',diagnosis_report_sha256=sha(args.diagnosis/'report.json'),
        diagnostic_arrays_sha256=sha(args.diagnosis/'diagnostic_arrays.npz'),plot_sha256=sha(args.out/'phase_representation.png'),
        values=values,limits=['Truth-based representation comparison, not an estimated model or vehicle-timbre acceptance'])
    print(json.dumps(dict(result=report['result'],plot_sha256=report['plot_sha256'])),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
