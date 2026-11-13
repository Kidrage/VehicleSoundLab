"""Plot conditional sideband evidence and the wrong-coordinate counterexample."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
args=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import sha


def load(path):return json.loads(path.read_text(encoding='utf-8'))
def magnitude(pair):return float(np.hypot(*pair))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-sideband-review/1',result='running',sources={},real_audio_read=False,
    model_exported=False,runtime_changed=False)
try:
    root=args.workspace/'references/analysis/F2_sideband_v1';actual=load(root/'observe1/report.json');audit=load(root/'audit1/report.json')
    spaces=load(root/'subspaces1/report.json');checked=load(root/'subspaces_audit1/report.json')
    assert audit['actual_report_sha256']==sha(root/'observe1/report.json')
    assert checked['actual_report_sha256']==sha(root/'subspaces1/report.json')
    fig,axes=plt.subplots(3,1,figsize=(12,11),layout='constrained')
    cases=actual['controls']['cases'];index=np.arange(len(cases));width=.34
    am=[magnitude(c['measurement']['parity'][0]['am_relative']) for c in cases]
    quadrature=[magnitude(c['measurement']['parity'][0]['quadrature_relative']) for c in cases]
    axes[0].bar(index-width/2,am,width,label='Amplitude-like parity |A|',color='#c78636')
    axes[0].bar(index+width/2,quadrature,width,label='Quadrature-like parity |P|',color='#336c98')
    axes[0].set(xticks=index,xticklabels=['Plain','AM','Quadrature','True PM','Upper tone','Paired tones = AM'],ylim=(0,.25),
        ylabel='Relative complex-coefficient magnitude',title='Known coordinates: pure AM and independent paired tones can have IDENTICAL parity')
    axes[0].legend(loc='upper center',ncol=2);axes[0].grid(axis='y',alpha=.2)
    x=np.arange(9);width=.25
    for shift,key,label,color in [(-width,'amplitude_reduction_percent','A only (+2m)','#c78636'),
        (0,'quadrature_reduction_percent','Q only (+2m)','#336c98'),(width,'joint_reduction_percent','Joint (+4m)','#6e8a6d')]:
        axes[1].bar(x+shift,[r['channels'][0][key] for r in spaces['observations']],width,label=label,color=color)
    axes[1].set(xticks=x,xticklabels=['%g-%g'%tuple(r['source_seconds']) for r in spaces['observations']],
        xlabel='Original source window (s)',ylabel='Conditional training-cost reduction (%)',ylim=(0,12),
        title='Actual source: Q-only lower cost in 9/9 windows; this does NOT establish physical FM')
    axes[1].legend();axes[1].grid(axis='y',alpha=.2)
    wrong=spaces['controls']['half_native_bin_wrong_coordinate_costs'];base=wrong['base']
    improvement=[100*(1-wrong[key]/base) for key in ('amplitude','quadrature','joint')]
    axes[2].bar(np.arange(3),improvement,color=['#c78636','#336c98','#6e8a6d'],width=.5)
    for i,value in enumerate(improvement):axes[2].text(i,value+max(improvement)*.04,f'{value:.2f}%',ha='center')
    axes[2].set(xticks=np.arange(3),xticklabels=['A only','Q only','Joint'],ylim=(0,max(improvement)*1.9),
        ylabel='Conditional training-cost reduction (%)',
        title='Counterexample: an unmodulated tone + wrong frequency coordinate also gains apparent detail')
    axes[2].text(.02,.9,'Input coordinate error: +0.5 Hz (original native-bin half-width)\nNo actual modulation was added to this signal.',transform=axes[2].transAxes,fontsize=10,va='top')
    axes[2].grid(axis='y',alpha=.2)
    fig.suptitle('F2 fixed 3 Hz sideband observations: coordinate calibration needed before generative DNA',fontsize=14)
    target=args.out/'F2_sideband_evidence.png';fig.savefig(target,dpi=150);plt.close(fig)
    for path in (Path(__file__),repo/'tools/drive_evidence_v1/sources.py'):
        relative=path.relative_to(repo);dest=args.out/'exact_sources'/relative;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);report['sources'][relative.as_posix()]=sha(path)
    report.update(result='conditional_sidebands_subspaces_and_wrong_coordinate_counterexample_plotted',plot_sha256=sha(target),
        reports_sha256={name:sha(root/name/'report.json') for name in ('observe1','audit1','subspaces1','subspaces_audit1')},
        limits=['Plot concerns low-order idle observations, not restored high-frequency timbre',
            'No source classifier, shared phase, new audio, C model or subjective acceptance'])
    print(json.dumps(dict(result=report['result'],plot=str(target))),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
