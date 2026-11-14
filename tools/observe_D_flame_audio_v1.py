"""Inspect the fixed approved D plume interval without creating an event voice."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flame_audio_v1.measure import observe,controls
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',inputs={},source_files={})
def consume(path):r['inputs'][str(path)]=sha(path);return path
try:
    for n in ['tools/observe_D_flame_audio_v1.py','tools/flame_audio_v1/measure.py','research/D_flame_audio_v1_plan.json']:
        dest=a.out/'exact_sources'/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/n,dest);r['source_files'][n]=sha(repo/n)
    plan=load(consume(repo/'research/D_flame_audio_v1_plan.json'))
    r['known_before_source']=controls(plan);save(a.out/'report.json',r)
    catalog=load(consume(repo/'references/segments_v1.json'));entry=catalog['sources']['D']
    approval=load(consume(a.workspace/'references/approval_manifest.json'))
    assert next(v for v in approval if v['id']=='D')['approved']
    for key in ['raw','master']:assert sha(consume(a.workspace/entry[key]))==entry[key+'_sha256']
    with sf.SoundFile(a.workspace/entry['master']) as f:
        assert f.samplerate==48000 and f.channels==2 and f.subtype=='FLOAT'
        first,stop=[round(t*48000) for t in plan['source_seconds']];f.seek(first);audio=f.read(stop-first,always_2d=True)
    assert len(audio)==8*48000 and np.isfinite(audio).all()
    sf.write(a.out/'native_reference.wav',audio,48000,subtype='FLOAT')
    values=observe(audio,plan);np.savez_compressed(a.out/'observations.npz',**values)
    times=values['time']+plan['source_seconds'][0];r['candidates']=[]
    for i in values['peaks']:
        r['candidates'].append(dict(source_seconds=float(times[i]),two_band_excess_db=float(values['score'][i]),
            all_band_excess_db=values['excess'][i].tolist(),raw_crest_LR=values['crest'][i].tolist(),
            label='Acoustic excess candidate only; no physical event/clean source label'))
    clips=[('whole',36,44),('before',36,38),('primary',38,42),('after',42,44)]
    r['clips']=[]
    for name,lo,hi in clips:
        clip=audio[round((lo-36)*48000):round((hi-36)*48000)].copy()*.5
        fade=.5-.5*np.cos(np.pi*np.arange(240)/240);clip[:240]*=fade[:,None];clip[-240:]*=fade[::-1,None]
        path=a.out/(name+'.wav');sf.write(path,clip,48000,subtype='FLOAT')
        r['clips'].append(dict(key=name,source_seconds=[lo,hi],frames=len(clip),file=path.name,sha256=sha(path)))
    whole_power=values['bands'].mean(axis=0);cross=values['cross'].mean(axis=0)
    coherence=cross/np.sqrt(whole_power[:,0]*whole_power[:,1])
    r['statistics']=dict(mean_band_power_LR=whole_power.tolist(),coherence_LR=[[float(v.real),float(v.imag)] for v in coherence],
        maximum_two_band_excess_db=float(values['score'].max()),candidate_count=len(r['candidates']),
        primary_candidate_count=sum(38<=v['source_seconds']<42 for v in r['candidates']),
        peak_FS=np.max(abs(audio),axis=0).tolist(),sample_count=len(audio))
    fig,axes=plt.subplots(3,1,figsize=(11,8),sharex=True,constrained_layout=True)
    for c in range(2):axes[0].plot(times,values['rms'][:,c],label='L' if c==0 else 'R',lw=.8)
    axes[0].set_ylabel('Raw RMS (FS)');axes[0].legend()
    for band,label in zip([3,4,5],['1.5-3k','3-6k','6-10k']):axes[1].plot(times,values['excess'][:,band],label=label,lw=.8)
    axes[1].axhline(6,color='black',ls='--',lw=.8);axes[1].set_ylabel('Above local median (dB)');axes[1].legend(ncol=3)
    mono=values['bands'].mean(axis=2)
    axes[2].imshow(10*np.log10(np.maximum(mono.T,1e-20)),origin='lower',aspect='auto',extent=[times[0],times[-1],-.5,6.5],cmap='magma')
    axes[2].set_yticks(range(7),['20-120','120-500','500-1.5k','1.5-3k','3-6k','6-10k','10-16k']);axes[2].set_ylabel('Band (Hz)');axes[2].set_xlabel('Source seconds')
    for ax in axes:
        ax.axvspan(38,42,color='steelblue',alpha=.1)
        for row in r['candidates']:ax.axvline(row['source_seconds'],color='tab:green',alpha=.5,lw=.8)
    fig.savefig(a.out/'diagnostic.png',dpi=150);plt.close(fig)
    r.update(result='fixed_window_observed',fitting_done=False,runtime_changed=False,
        decision='Numerical candidates do not establish isolated pops; raw listening and independent context/source support remain required',
        preserved_gain=.5,room_added=False,PCM_loop_created=False,measured_RPM=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r['statistics'],flush=True)
