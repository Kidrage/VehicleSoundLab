"""Audit all three apertures by direct demodulation; characterize rejected ones."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','fit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for k in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[k]='2'
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
from stationary_bridge_v1.diagnose import carrier_diagnostics
from stationary_bridge_v1.extract import compile_anchor
a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',inputs={},sources={},observations=[])
try:
    for n in ['tools/audit_stationary_bridge_v1.py','tools/stationary_bridge_v1/diagnose.py',
              'tools/stationary_bridge_v1/extract.py','tools/sound_dna/windowed.py',
              'tools/sound_dna/statistics.py','tools/exterior_clock_v1/warp.py','tools/research_archive_v1.py']:
        dest=a.out/'exact_sources'/n;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/n,dest);r['sources'][n]=sha(repo/n)
    # Known complete-window phases and amplitudes before source observation.
    t=np.arange(18*1024);known=np.zeros((len(t),2))
    for order in (3,5,7):
        for c in (0,1):known[:,c]+=(.07+.01*order)*np.cos(2*np.pi*order*t/1024+.13*order+.4*c)
    k=carrier_diagnostics(known)
    assert all(min(row['coherence'])>1-1e-12 for row in k['orders'].values())
    r['known_before_source']=k
    # Subsequent diagnosis, declared after the real-source rejection: a rapid
    # analytic falling clock with CONSTANT known harmonic phase/amplitudes.
    # This is not a retroactive pre-fit qualification or a complete phase proof.
    plan=load(repo/'research/stationary_bridge_v1_plan.json')
    seconds=np.arange(3*48000)/48000
    phase=80/.6*(1-np.exp(-.6*seconds));known=np.zeros((len(seconds),2))
    for order in (3,5,7):
        for c in (0,1):known[:,c]+=(.07+.01*order)*np.cos(2*np.pi*order*phase+.13*order+.4*c)
    clock=[dict(seconds=float(t),root_hz=float(80*np.exp(-.6*t)*1.008)) for t in np.arange(.2,2.801,.01)]
    r['subsequent_rapid_fall_controls']=[]
    for target in (36.,41.,54.):
        _,_,wave,positions,meta=compile_anchor(known,0,clock,target,plan)
        q=80/.6*(1-np.exp(-.6*positions))
        deviation=float(np.std(q-np.arange(len(wave))/1024))
        assert deviation<.002 and min(v for c in meta['heldout_coherence'].values() for v in c)>.99
        r['subsequent_rapid_fall_controls'].append(dict(target_root_hz=target,cycle_std=deviation,heldout_coherence=meta['heldout_coherence']))
    fit=load(a.fit/'report.json');r['inputs'][str(a.fit/'report.json')]=sha(a.fit/'report.json')
    assert fit['result']=='qualified_bridge_voices_rendered'
    fig,axes=plt.subplots(3,2,figsize=(11,8),layout='constrained')
    for i,name in enumerate(load(repo/'research/stationary_bridge_v1_plan.json')['names']):
        folder=a.fit/name;meta=load(folder/'extraction.json');path=folder/'normalized.wav'
        r['inputs'][str(path)]=sha(path);r['inputs'][str(folder/'extraction.json')]=sha(folder/'extraction.json')
        wave,rate=sf.read(path,always_2d=True);assert rate==48000
        result=carrier_diagnostics(wave)
        for order in ('3','7'):
            assert np.max(abs(np.array(result['orders'][order]['coherence'])-meta['heldout_coherence'][order]))<1e-7
        result.update(name=name,root_hz=meta['root_hz'],qualified=any(v['name']==name for v in fit['anchors']))
        r['observations'].append(result)
        for order,data in result['orders'].items():
            time=np.array(data['centers'])/48000
            axes[i,0].plot(time,np.array(data['magnitude'])[:,0],label='line '+order)
            axes[i,1].plot(time,np.array(data['phase_radians'])[:,0],label='line '+order)
        axes[i,0].set(title=name+(' | retained' if result['qualified'] else ' | NOT retained'),xlabel='Normalized seconds',ylabel='Carrier amplitude, left')
        axes[i,1].set(xlabel='Normalized seconds',ylabel='Phase change, radians, left')
        for ax in axes[i]:ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.savefig(a.out/'carrier_drift.png',dpi=130);plt.close(fig)
    r.update(result='passed',scope='Checks measurement arithmetic and preserves actual drift; does not prove its physical cause, phase-model validity or timbre acceptance')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
