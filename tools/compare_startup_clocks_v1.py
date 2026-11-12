"""Expose local clock disagreement hidden by whole-segment phase coherence."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import read,sha
from exterior_clock_v1.warp import warp
from phase_clock_v1.projection import polish
from startup_catch_v1.clock import diagnostics,frequency,agreement
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_comparison.py')
shutil.copy2(repo/'tools/startup_catch_v1/clock.py',a.out/'clock.py')
r=dict(result='running',source_sha256=sha(__file__),candidates=[],pairs=[])
try:
    x,meta=read(a.workspace,'A_start_context','audio_onset_observation');r['input']=meta
    previous=a.workspace/'references/analysis/startup_catch_v1/settle1/report.json'
    source=json.loads(previous.read_text(encoding='utf-8'));path=source['path']['rows']
    r['prior_report_sha256']=sha(previous)
    times=np.array([v['seconds'] for v in path]);root=np.array([v['root_hz'] for v in path])
    y,p,info=warp(x,33,times,root,float(times[0]),float(times[-1]))
    found={};fig,ax=plt.subplots(figsize=(12,4),constrained_layout=True)
    for reference in (2,3,5):
        polished,pos,qual=polish(x,33,y,p,reference,info['source_cutoff_hz'])
        measured=diagnostics(polished,reference);t,f=frequency(pos)
        np.savez_compressed(a.out/f'ref{reference}.npz',normalized=polished,positions=pos)
        r['candidates'].append(dict(reference=reference,phase=qual,diagnostics=measured,
            frequency_quantiles=np.percentile(f,[0,1,50,99,100]).tolist()))
        found[reference]=pos;ax.plot(t,f,label=f'Independent phase reference {reference}')
    for first,second in ((2,3),(2,5),(3,5)):
        r['pairs'].append(dict(references=[first,second],**agreement(found[first],found[second],38.42,39.57)))
    ax.set(xlabel='Decoded source seconds',ylabel='Inferred acoustic Hz',title='Local frequency estimates: whole-segment coherence can hide a phase glitch')
    ax.legend();fig.savefig(a.out/'independent_clocks.png',dpi=140);plt.close(fig)
    r['result']='local_comparison_complete'
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],pairs=r['pairs'],candidates=[dict(reference=v['reference'],frequency_quantiles=v['frequency_quantiles']) for v in r['candidates']])))
