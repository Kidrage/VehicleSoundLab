"""Actual adaptive authoring, old v2 reproducibility and unchanged C execution."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil
import numpy as np
import soundfile as sf
from author_event import author
from event_authoring.native import Renderer
from event_authoring.model import synth
from event_authoring.contour_knots import propose
from research_archive_v1 import load,save,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False);repo=Path(__file__).resolve().parents[1]
    root=Path('E:/VehicleSoundLab/references/analysis');renderer=Renderer(repo);cases=[]
    shutil.copy2(__file__,out/'executed_verification.py')
    for key in ('A','B'):
        previous=load(root/f'event_joint_v1/verification2/{key}/analysis/profile.json')
        folder=out/key;folder.mkdir();job=deepcopy(previous['source_job'])
        job.update(schema='vsl.event-authoring-job/7',envelope_fit='band-contour-v3',name=key+'启动 · 自适应控制点候选')
        save(folder/'job.json',job);result=author(folder/'job.json',folder/'analysis')
        assert result.get('status')!='analysis_only',result
        candidate=load(folder/'analysis/profile.json');p=candidate['parameters'];prior=previous['parameters']
        assert candidate['fit']['contour_fit']['adaptive_selected']
        for kind in ('modes','bands'):
            assert len(p[kind])==len(prior[kind])
            for before,after in zip(prior[kind],p[kind]):
                assert {k:v for k,v in before.items() if k!='amplitude'}=={k:v for k,v in after.items() if k!='amplitude'}
        assert len(p['contours'])==len(prior['contours'])
        if key=='B':assert [(c['low_hz'],c['high_hz']) for c in p['contours']]==[(4500,14000)]
        for c in p['contours']:
            assert 2<=len(c['seconds'])<=8 and c['seconds'][0]==0 and c['seconds'][-1]<=5
            assert np.min(np.diff(c['seconds']))>=.01-1e-12
        duration=job['seconds'][1]-job['seconds'][0];seeds=[]
        for seed in (27431,48271,93931,17389):
            values=dict(seconds=1.2,hold_seconds=duration,seed=seed)
            x,report=renderer.render(p,job['kind'],values)
            y=synth(p,seed=seed,seconds=1.2,release_at=duration if p['gated'] else None);y=np.pad(y,(0,len(x)-len(y)))
            error=float(np.max(abs(x-y)));assert error<3e-7
            sf.write(folder/f'C-{seed}.wav',x,48000,subtype='FLOAT');save(folder/f'C-{seed}.json',report)
            seeds.append(dict(seed=seed,independent_model_error=error))
        for pitch,decay in ((.8,.7),(1.2,1.5)):
            x,_=renderer.render(p,job['kind'],dict(seconds=1.2,hold_seconds=.35,pitch=pitch,decay=decay))
            y=synth(p,seconds=1.2,release_at=.35 if p['gated'] else None,pitch=pitch,decay=decay)
            y=np.pad(y,(0,len(x)-len(y)));assert np.max(abs(x-y))<3e-7
            if p['gated']:assert not np.any(x[18001:])
        save(folder/'old.job.json',previous['source_job']);author(folder/'old.job.json',folder/'old-v2')
        assert load(folder/'old-v2/profile.json')['parameters']==prior
        cases.append(dict(key=key,seeds=seeds,contour_fit=candidate['fit']['contour_fit'],old_v2_parameters_exact=True))
        print(key,'actual adaptive authoring and C passed',flush=True)
    # A narrow, delayed synthetic amplitude shape should attract coarse knots.
    t=np.arange(150)*.005+1024/48000;power=np.exp(-((t-.12)/.015)**2)+.03
    knots=propose(t,power,.8);assert len(knots)==8 and knots[0]==0 and knots[-1]==.8
    assert min(abs(np.array(knots)-.12))<.01
    np.testing.assert_allclose(propose(t,power*7,.8),knots,rtol=0,atol=1e-15)
    runtime=[p for group in ('src','modules','voices') for p in (repo/group).rglob('*')
        if p.is_file() and (p.suffix in ('.c','.h') or group=='voices')]
    frozen=Path('E:/VehicleSoundLab/baselines/event_joint_v1/delivery1/evidence/startup1/exact_sources')
    assert len(runtime)==459 and all(sha(p)==sha(frozen/p.relative_to(repo)) for p in runtime)
    save(out/'report.json',dict(result='passed',cases=cases,known_delayed_burst_knots=True,
        absolute_power_scale_does_not_change_knot_times=True,source_components_and_capacity_unchanged=True,
        runtime_and_voices_unchanged=len(runtime),author_bridge_sha256=renderer.identity,timbre_accepted=False))


if __name__=='__main__':main()
