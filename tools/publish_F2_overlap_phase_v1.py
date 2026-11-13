"""Plot known precision repair and persistent real overlap differences."""
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
report=dict(schema='vsl.F2-overlap-phase-review/1',result='running',sources={},real_audio_read=False,
    model_exported=False,runtime_changed=False)
try:
    root=args.workspace/'references/analysis/F2_overlap_phase_v1'
    actual=json.loads((root/'observe2/report.json').read_text(encoding='utf-8'))
    audit=json.loads((root/'audit1/report.json').read_text(encoding='utf-8'))
    assert audit['actual_report_sha256']==sha(root/'observe2/report.json')
    c=actual['controls'];old=c['original_overlap_control']['estimator_control'];new=c['precision_overlap']
    fig,axes=plt.subplots(3,1,figsize=(12,11),layout='constrained');x=np.arange(2);width=.35
    axes[0].bar(x-width/2,old['waveform_relative_errors'],width,label='Original observed-initialized fit',color='#ae7041')
    axes[0].bar(x+width/2,new['waveform_relative_errors'],width,label='One bounded correction',color='#386c9a')
    axes[0].axhline(1e-6,color='#9c4141',ls=':',label='Unchanged known-control threshold')
    axes[0].set(xticks=x,xticklabels=['Known window 0-1 s','Known window 0.5-1.5 s'],yscale='log',ylim=(1e-16,1e-3),
        ylabel='Relative waveform error',title='Known continuous source: repair inclusive-endpoint precision; original failed control retained')
    axes[0].legend(fontsize=9);axes[0].grid(axis='y',alpha=.2)
    rows=actual['observations'];x=np.arange(len(rows));width=.24;colors=['#386c9a','#a27633','#54845e']
    labels=['%g-%g'%tuple(r['source_overlap_seconds']) for r in rows]
    for j,color in enumerate(colors):
        shift=(j-1)*width
        for ax,key in ((axes[1],'wrapped_phase_rms_cycles'),(axes[2],'frequency_difference_max_Hz')):
            before=[r['channels'][0]['comparisons'][j]['old'][key] for r in rows]
            after=[r['channels'][0]['comparisons'][j]['new'][key] for r in rows]
            ax.bar(x+shift,after,width,label='Main slot '+str(j+1),color=color,alpha=.85)
            ax.plot(x+shift,before,'_',color='black',ms=10,label='Parent fits' if j==0 else None)
    axes[1].set(xticks=x,xticklabels=labels,ylim=(0,.15),ylabel='Wrapped phase RMS difference (cycles)',
        title='Actual source: local phase disagreement persists; correction and parent markers nearly coincide')
    axes[2].set(xticks=x,xticklabels=labels,ylim=(0,2.6),ylabel='Maximum frequency difference (Hz)',
        xlabel='Shared original source interval (s)',title='Actual source: independent quadratic fits disagree within their shared samples')
    for ax in axes[1:]:ax.legend(ncol=4,fontsize=9);ax.grid(axis='y',alpha=.2)
    fig.suptitle('F2 local continuity diagnosis: shared samples, no phase alignment, no new DNA or physical-clock claim',fontsize=13)
    target=args.out/'F2_overlap_phase.png';fig.savefig(target,dpi=150);plt.close(fig)
    for path in (Path(__file__),repo/'tools/drive_evidence_v1/sources.py'):
        relative=path.relative_to(repo);dest=args.out/'exact_sources'/relative;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);report['sources'][relative.as_posix()]=sha(path)
    report.update(result='known_precision_repair_and_persistent_real_overlap_disagreement_plotted',plot_sha256=sha(target),
        reports_sha256={n:sha(root/n/'report.json') for n in ('observe1','observe2','audit1')},
        limits=['Left channel shown; both channels independently checked numerically, not independent recordings',
            'Shared-sample consistency is not measured phase accuracy or common-clock qualification',
            'No phase alignment or interpolation across touching window gaps'])
    print(json.dumps(dict(result=report['result'],plot=str(target))),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
