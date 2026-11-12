"""Compare slow independent phase clocks before authoring a cabin DNA candidate."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import read,sha
from exterior_clock_v1.warp import warp
from startup_catch_v1.slow_phase import polish
from startup_catch_v1.clock import diagnostics,frequency,agreement
from phase_clock_v1.projection import independent_agreement
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
a.out.mkdir(parents=True,exist_ok=False)
for path in [Path(__file__),*Path(__file__).with_name('startup_catch_v1').glob('*.py')]:
    shutil.copy2(path,a.out/path.name)
r=dict(result='running',source_sha256=sha(__file__),candidates=[],pairs=[],controls=[])
try:
    # Independent known chirps verify the bounded slow-coordinate scope.
    rate=48000;t=np.arange(3*rate)/rate
    for number in range(6):
        hz=35*(1+.02*np.sin(2*np.pi*(.4+number*.08)*t))
        phase=np.r_[0,np.cumsum((hz[:-1]+hz[1:])/(2*rate))]
        signal=np.column_stack([sum((.1/k)*np.cos(2*np.pi*k*phase+.2*k+c*.13) for k in (2,3,5,7)) for c in (0,1)])
        # Supply only a constant coarse clock: the phase observer must recover
        # the known varying coordinate rather than receive its answer as input.
        normalized,positions,info=warp(signal,0,t,np.full(len(t),35.),.25,2.75)
        refined,pos,qual=polish(signal,0,normalized,positions,2,info['source_cutoff_hz'])
        at,observed=frequency(pos);truth=np.interp(at,t,hz)
        error=float(np.max(abs(observed-truth)));assert error<.06
        r['controls'].append(dict(kind='known slow chirp from constant coarse clock',number=number,
            coarse_hz=35,max_hz_error=error))
    # A separate, detuned fifth line must not qualify as a common engine clock.
    # A failure of support/connected-phase is also a valid rejection.
    phase=35*t
    altered=np.column_stack([sum((.1/k)*np.cos(2*np.pi*k*phase*(1.18 if k==5 else 1)+.2*k+c*.13)
                                 for k in (2,3,5,7)) for c in (0,1)])
    yn,pn,info=warp(altered,0,t,np.full(len(t),35.),.25,2.75)
    try:
        _,pa,_=polish(altered,0,yn,pn,2,info['source_cutoff_hz'])
        _,pb,_=polish(altered,0,yn,pn,5,info['source_cutoff_hz'])
        negative=agreement(pa,pb,.5,2.5);assert not negative['passed']
        r['controls'].append(dict(kind='known detuned independent fifth',rejected=True,comparison=negative))
    except ValueError as exc:
        r['controls'].append(dict(kind='known detuned independent fifth',rejected=True,reason=str(exc)))
    x,meta=read(a.workspace,'A_start_context','audio_onset_observation');r['input']=meta
    previous=a.workspace/'references/analysis/startup_catch_v1/settle1/report.json'
    path=json.loads(previous.read_text(encoding='utf-8'))['path']['rows'];r['prior_report_sha256']=sha(previous)
    times=np.array([v['seconds'] for v in path]);root=np.array([v['root_hz'] for v in path])
    normalized,positions,info=warp(x,33,times,root,float(times[0]),float(times[-1]))
    found={};fig,ax=plt.subplots(figsize=(12,4),constrained_layout=True)
    for reference in (2,3,5):
        y,pos,qual=polish(x,33,normalized,positions,reference,info['source_cutoff_hz'])
        measured=diagnostics(y,reference);at,observed=frequency(pos)
        file=a.out/f'ref{reference}.npz';np.savez_compressed(file,normalized=y,positions=pos)
        r['candidates'].append(dict(reference=reference,phase=qual,diagnostics=measured,
            independent_agreement=independent_agreement(measured),npz=file.name,sha256=sha(file)))
        found[reference]=pos;ax.plot(at,observed,label=f'Phase reference {reference}')
    for first,second in ((2,3),(2,5),(3,5)):
        r['pairs'].append(dict(references=[first,second],**agreement(found[first],found[second],38.48,39.51)))
    ax.set(xlabel='Decoded source seconds',ylabel='Acoustic Hz',title='Four-cycle slow phase estimates; no physical RPM identification');ax.legend()
    fig.savefig(a.out/'slow_clocks.png',dpi=140);plt.close(fig)
    r['result']='slow_observation_complete'
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],pairs=r['pairs'],candidates=[dict(reference=v['reference'],phase=v['phase'],agreement=v['independent_agreement']) for v in r['candidates']])))
