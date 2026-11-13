"""Plot known affine-AM recovery and the unchanged real-recording limitations."""
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
from matplotlib.colors import ListedColormap
from drive_evidence_v1.sources import sha


def load(path):return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-local-envelopes-review/1',result='running',sources={},real_audio_read=False,
    model_exported=False,runtime_changed=False)
try:
    root=args.workspace/'references/analysis/F2_local_envelopes_v1';actual=load(root/'observe2/report.json');audit=load(root/'audit2/report.json')
    assert audit['actual_report_sha256']==sha(root/'observe2/report.json')
    known=[c for c in actual['controls']['cases'] if c['gate_applied']]
    fig,axes=plt.subplots(3,1,figsize=(11,12),layout='constrained',gridspec_kw={'height_ratios':[1,1,1.5]})
    index=np.arange(len(known));width=.34
    axes[0].bar(index-width/2,[max(1e-15,c['constant']['waveform_relative_error']) for c in known],width,label='Constant amplitudes',color='#bd672d')
    axes[0].bar(index+width/2,[max(1e-15,c['affine']['waveform_relative_error']) for c in known],width,label='Positive affine amplitudes',color='#326c92')
    axes[0].set(xticks=index,xticklabels=[c['id'].replace('_',' ') for c in known],yscale='log',ylim=(1e-15,1),
        ylabel='Unweighted relative waveform error',title='Known, model-matched fixtures: affine recovery works; not recording validation')
    axes[0].legend();axes[0].grid(axis='y',alpha=.2)
    windows=['%g-%g'%tuple(r['source_seconds']) for r in actual['observations']]
    values=[c['left_cost_reduction_percent'] for c in audit['comparisons']]
    colors=['#326c92' if all(c['new_channel_success']) else '#d3a139' for c in audit['comparisons']]
    axes[1].bar(np.arange(9),values,color=colors)
    for i,v in enumerate(values):axes[1].text(i,v+.008,f'{v:.3f}%',ha='center',fontsize=9)
    axes[1].set(xticks=np.arange(9),xticklabels=windows,ylim=(0,.46),xlabel='Original source window (s)',
        ylabel='Weighted training-cost reduction (%)',title='Actual source: all nine fixed comparisons improve by less than 0.4%; amber = max60 exhausted')
    axes[1].grid(axis='y',alpha=.2)
    state=[];labels=[]
    for row in actual['observations']:
        fit=row['fits'][0]['affine_fit'];b=fit['at_bound'][:3];s=any(fit['slope_at_bound']);success=fit['success']
        state.append([int(v) for v in b]+[int(s),0 if success else 2])
        labels.append(['BOUND' if v else 'inside' for v in b]+['BOUND' if s else 'inside','OK' if success else 'max60'])
    axes[2].imshow(state,cmap=ListedColormap(['#e1ece8','#e7b1a8','#ecd5a0']),vmin=0,vmax=2,aspect='auto')
    axes[2].set(xticks=np.arange(5),xticklabels=['75 Hz: f / q','112 Hz: f / q','187 Hz: f / q','Any amplitude slope','Solver success'],
        yticks=np.arange(9),yticklabels=windows,xlabel='Bounds and success are separate; inside does NOT prove adequate model',
        title='Actual left-channel status (right independently audited): successful main rows 5 -> 4')
    for i,row in enumerate(labels):
        for j,value in enumerate(row):axes[2].text(j,i,value,ha='center',va='center',fontsize=10)
    fig.suptitle('F2 positive local envelopes: useful controlled model; NOT adopted as idle DNA',fontsize=14)
    target=args.out/'F2_local_envelopes.png';fig.savefig(target,dpi=150);plt.close(fig)
    for path in (Path(__file__),repo/'tools/drive_evidence_v1/sources.py'):
        relative=path.relative_to(repo);dest=args.out/'exact_sources'/relative;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);report['sources'][relative.as_posix()]=sha(path)
    report.update(result='known_envelopes_and_all9real_limitations_plotted',plot_sha256=sha(target),
        input_report_sha256=sha(root/'observe2/report.json'),audit_report_sha256=sha(root/'audit2/report.json'),
        limits=['Original failure and audit1 retained; audit2 separates raw bounds from optimizer success',
            'No new audio, shared phase, physical-state inference or perceptual acceptance'])
    print(json.dumps(dict(result=report['result'],plot=str(target))),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
