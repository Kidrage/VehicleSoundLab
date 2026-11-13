"""Plot known chirp clipping, changed-prior boundaries and persistent Q residuals."""
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


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-rate-coordinates-review/1',result='running',sources={},real_audio_read=False,
    model_exported=False,runtime_changed=False)
try:
    root=args.workspace/'references/analysis/F2_rate_coordinates_v1';actual=load(root/'observe1/report.json');audit=load(root/'audit1/report.json');diagnosis=load(root/'diagnosis2/report.json')
    assert audit['actual_report_sha256']==sha(root/'observe1/report.json')
    fig,axes=plt.subplots(3,1,figsize=(12,11),layout='constrained');width=.35
    index=np.arange(3)
    axes[0].bar(index-width/2,[r['waveform_relative_error'] for r in diagnosis['cases']],width,label='Old flat q bound',color='#b66636')
    axes[0].bar(index+width/2,[r['waveform_relative_error'] for r in actual['controls']['cases']],width,label='Reference-rate bound',color='#366e99')
    axes[0].set(xticks=index,xticklabels=['Within old bound','Positive crossing','Negative crossing'],yscale='log',ylim=(1e-15,1),
        ylabel='Relative waveform error',title='Known smooth harmonic rises/falls: no extra 3 Hz modulation; old crossing error ~11.5%')
    axes[0].legend();axes[0].grid(axis='y',alpha=.2)
    x=np.arange(9);windows=['%g-%g'%tuple(r['source_seconds']) for r in actual['observations']]
    old=[sum(row['channels'][0]['old_fit']['at_bound'][:3]) for row in actual['observations']]
    new=[sum(row['channels'][0]['new_fit']['at_bound'][:3]) for row in actual['observations']]
    axes[1].bar(x-width/2,old,width,label='Old main-line bounds',color='#b66636')
    axes[1].bar(x+width/2,new,width,label='New main-line bounds',color='#366e99')
    axes[1].set(xticks=x,xticklabels=windows,yticks=[0,1,2,3],ylim=(0,3.5),xlabel='Original source window (s)',
        ylabel='Bound main components (left channel)',title='Actual source: changed engineering prior clears main flags; NOT an accuracy or complete-DNA claim')
    axes[1].legend();axes[1].grid(axis='y',alpha=.2)
    before=[row['channels'][0]['old_subspace_summary']['quadrature_reduction_percent'] for row in actual['observations']]
    after=[row['channels'][0]['quadrature_reduction_percent'] for row in actual['observations']]
    axes[2].bar(x-width/2,before,width,label='Old coordinates',color='#b66636')
    axes[2].bar(x+width/2,after,width,label='New coordinates',color='#366e99')
    axes[2].set(xticks=x,xticklabels=windows,ylim=(0,10),xlabel='Original source window (s)',
        ylabel='Q-only gain (% of each own base cost)',title='Actual source: conditional quadrature residual largely persists after main-bound correction')
    axes[2].legend();axes[2].grid(axis='y',alpha=.2)
    fig.suptitle('F2 local reference-rate coordinates: 18 local fits + 72 subspaces audited; no new audio or DNA',fontsize=14)
    target=args.out/'F2_rate_coordinates.png';fig.savefig(target,dpi=150);plt.close(fig)
    for path in (Path(__file__),repo/'tools/drive_evidence_v1/sources.py'):
        relative=path.relative_to(repo);dest=args.out/'exact_sources'/relative;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);report['sources'][relative.as_posix()]=sha(path)
    report.update(result='known_clipping_changed_prior_and_persistent_residual_plotted',plot_sha256=sha(target),
        reports_sha256={name:sha(root/name/'report.json') for name in ('diagnosis1','diagnosis2','observe1','audit1')},
        limits=['Reference-rate law is an engineering prior; nine within-main-bound windows do not certify true phase or naturalness',
            'Other components still saturate; conditional Q fractions have different own-base denominators',
            'No high-frequency recovery or new synthesis'])
    print(json.dumps(dict(result=report['result'],plot=str(target))),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
