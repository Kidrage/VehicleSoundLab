"""All declared fresh idle excitation candidates, with unchanged spectral profiles."""
import argparse
import shutil
import sys
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from research_archive_v1 import load,save,sha
from idle_modal_v1.modal import render
from idle_excitation_moments_v1.excitation import streams,blend
from idle_excitation_moments_v1.moments import observe

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},renders=[])
try:
    parent=load(a.input/'report.json');assert parent['result']=='moment_candidate_compiled'
    plan=parent['plan'];profile=load(parent['profile_path']);model=load(a.input/'model.json')
    assert sha(parent['profile_path'])==parent['profile_sha256']
    for path in [Path(__file__),repo/'tools/idle_excitation_moments_v1/excitation.py',
                 repo/'tools/idle_excitation_moments_v1/moments.py',repo/'tools/sustain_osc_v1/oracle.py',
                 repo/'tools/idle_modal_v1/modal.py']:
        dest=a.out/'exact_sources'/path.relative_to(repo);dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][path.relative_to(repo).as_posix()]=sha(path)
    frames=plan['seconds']*48000;count=frames+profile['warmup_frames']
    main=render(profile['modal'],frames,48000)
    sf.write(a.out/'main.wav',main,48000,subtype='FLOAT')
    sos=np.load(a.input/'training.npz')['sos']
    mapping=dict(zip(model['kernel_indices'],model['probability']))
    for seed in plan['seeds']:
        textures={amount:np.zeros_like(main) for amount in plan['amounts']}
        events={}
        for i,kernel in enumerate(profile['kernels']):
            gaussian,sparse,event_count=streams(seed,i,count,mapping.get(i,1.))
            events[str(i)]=event_count
            for amount,detail in textures.items():
                noise=blend(gaussian,sparse,amount if i in mapping else 0.)
                y=signal.oaconvolve(noise,np.array(kernel['taps']))[profile['warmup_frames']:count]*kernel['gain']
                detail+=y[:,None]*np.array([[1.,kernel['right_over_left']]])
        for amount,detail in textures.items():
            tag=f'{round(amount*100):03d}_{seed}';mix=main+detail
            assert np.isfinite(mix).all() and np.max(abs(mix))<1.,'Unsafe FLOAT peak; do not normalize it away'
            for name,y in [('mix',mix),('detail',detail)]:
                sf.write(a.out/f'{name}_{tag}.wav',y,48000,subtype='FLOAT')
            zero_exact=None
            if amount==0:
                old=a.workspace/f'baselines/idle_texture_v2/evidence/trial1/fine_{seed}.wav'
                old_audio,rate=sf.read(old,always_2d=True)
                assert rate==48000 and np.array_equal(mix.astype(np.float32),old_audio.astype(np.float32))
                zero_exact=True
            statistics,_=observe(mix,sos,plan['trim_frames'])
            r['renders'].append(dict(tag=tag,seed=seed,amount=amount,peak=float(abs(mix).max()),
                statistics=statistics,zero_FLOAT_exact=zero_exact,events=events,
                mix_sha256=sha(a.out/f'mix_{tag}.wav'),detail_sha256=sha(a.out/f'detail_{tag}.wav')))
        print(dict(seed=seed,stage='all_amounts_rendered'),flush=True)
    r.update(result='sparse_excitation_candidates_pending_listening',observation=str(a.input),
             observation_sha256=sha(a.input/'report.json'),model_sha256=sha(a.input/'model.json'),
             profile_sha256=parent['profile_sha256'],runtime_changed=False,all_seeds_retained=True,
             synthesis_is_continuous=True,parameters_only_no_recorded_timeline=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],renders=len(r['renders']),max_peak=max(x['peak'] for x in r['renders'])),flush=True)
