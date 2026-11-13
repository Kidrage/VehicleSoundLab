"""Plot fixed variation geometry and conditional omitted-line errors."""
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


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-variation-projection-review/1',result='running',sources={},real_audio_read=False,
    model_exported=False,runtime_changed=False)
try:
    root=args.workspace/'references/analysis/F2_variation_projection_v1'
    actual=json.loads((root/'observe1/report.json').read_text(encoding='utf-8'))
    audit=json.loads((root/'audit1/report.json').read_text(encoding='utf-8'))
    assert audit['actual_report_sha256']==sha(root/'observe1/report.json')
    fig,axes=plt.subplots(3,1,figsize=(12,10.5),layout='constrained');width=.34;x=np.arange(2)
    cases=actual['controls']['cases'];names=['harmonic_hypothesis','equal_Hz'];labels=['Fixed 2/3/5 hypothesis','Equal-Hz hypothesis'];colors=['#386c9a','#ad7545']
    for shift,name,label,color in zip((-.5,.5),names,labels,colors):
        values=[100*c['observations'][name]['residual_squared_fraction'] for c in cases]
        axes[0].bar(x+shift*width,values,width,label=label,color=color)
    axes[0].set(xticks=x,xticklabels=['Known common cubic','Known independent neighbor'],ylim=(0,105),
        ylabel='Residual squared fraction (%)',title='Two fixed known examples: signatures differ; no classifier threshold or physical-source identity')
    axes[0].annotate('1.54e-7%',(-width/2,0),xytext=(0,5),textcoords='offset points',ha='center',fontsize=9)
    axes[0].legend(fontsize=9);axes[0].grid(axis='y',alpha=.2)
    rows=actual['observations'];x=np.arange(len(rows));ticks=['%g-%g'%tuple(r['source_overlap_seconds']) for r in rows]
    for shift,name,label,color in zip((-.5,.5),names,labels,colors):
        values=[100*r['channels'][0]['observations'][name]['residual_squared_fraction'] for r in rows]
        axes[1].bar(x+shift*width,values,width,label=label,color=color)
    axes[1].set(xticks=x,xticklabels=ticks,ylim=(0,20),ylabel='Residual squared fraction (%)',
        title='Actual model disagreements favor 2/3/5 geometry in all six pairs; NOT separated sound energy')
    axes[1].legend(fontsize=9);axes[1].grid(axis='y',alpha=.2)
    width=.24
    for j,color in enumerate(('#386c9a','#a27633','#54845e')):
        values=[r['channels'][0]['observations']['harmonic_hypothesis']['omitted_line_prediction_rms_error_Hz'][j] for r in rows]
        axes[2].bar(x+(j-1)*width,values,width,label='Omitted main slot '+str(j+1),color=color)
    axes[2].set(xticks=x,xticklabels=ticks,ylim=(0,.25),ylabel='Conditional prediction RMS error (Hz)',
        xlabel='Shared original source interval (s)',title='Omit one line in the fixed projection: joint parent fits/shared samples are NOT independent heldouts')
    axes[2].legend(ncol=3,fontsize=9);axes[2].grid(axis='y',alpha=.2)
    fig.suptitle('F2 variation geometry: fixed hypotheses, left channel shown, both channels audited, no clock or DNA export',fontsize=13)
    target=args.out/'F2_variation_projection.png';fig.savefig(target,dpi=150);plt.close(fig)
    for path in (Path(__file__),repo/'tools/drive_evidence_v1/sources.py'):
        relative=path.relative_to(repo);dest=args.out/'exact_sources'/relative;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);report['sources'][relative.as_posix()]=sha(path)
    report.update(result='known_signatures_real_fixed_geometry_and_conditional_errors_plotted',plot_sha256=sha(target),
        reports_sha256={name:sha(root/name/'report.json') for name in ('observe1','audit1')},
        limits=['Two known examples are not a general source classifier; proportional independent programs can be identical',
            'Residual fractions describe model-frequency disagreements, not acoustic source power',
            'No physical harmonic order, measured RPM, independent validation, new DNA or high-frequency recovery'])
    print(json.dumps(dict(result=report['result'],plot=str(target))),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
