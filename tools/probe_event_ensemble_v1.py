"""Known finite-power controls and exact existing-material ensemble candidates."""
import argparse
from copy import deepcopy
import importlib.util
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from event_authoring.audio import read
from event_authoring.measure import observe
from event_authoring.fit import fit
from event_authoring.model import synth
from event_authoring.native import Renderer,controls
from event_authoring import response_fit
from event_authoring.response_ensemble import (TRAIN_SEEDS,HELD_OUT_SEEDS,band_powers,
    finite_basis,objective,calibrate,search)
from research_archive_v1 import load,save,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    report=dict(result='running',goal_complete=False,timbre_accepted=False)
    for path in [Path(__file__),repo/'research/event_ensemble_v1_plan.json',
                 *sorted((repo/'tools/event_authoring').glob('*.py'))]:
        target=out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    try:
        known=dict(gated=0,duration_seconds=.16,attack_seconds=.001,release_seconds=.01,sweep_seconds=0.,level=1.,
            modes=[dict(hz=f,end_hz=f,phase=p,amplitude=a,decay_seconds=t) for f,p,a,t in
                   [(130.,.2,.2,.07),(420.,1.,.08,.025),(1900.,2.,.03,.009)]],
            bands=[dict(hz=f,q=q,amplitude=a,attack_seconds=.001,decay_seconds=.03) for f,q,a in
                   [(1450.,1.2,.04),(6200.,.8,.03)]])
        members,gram=finite_basis(known,.16);gain=np.array([.7,1.4,.8,1.2,.5])
        changed=deepcopy(known)
        for g,(kind,index) in zip(gain,members):changed[kind][index]['amplitude']*=float(g)
        predicted=np.einsum('i,sbij,j->sb',gain,gram,gain)
        direct=np.array([band_powers(synth(changed,seed=seed)) for seed in TRAIN_SEEDS])
        assert np.allclose(predicted,direct,rtol=2e-11,atol=1e-17)
        targets=np.mean([band_powers(synth(known,seed=seed)) for seed in TRAIN_SEEDS],axis=0)
        residual,jacobian=objective(gram,targets)
        numerical=np.column_stack([(residual(gain+np.eye(len(gain))[i]*1e-5)-
                                    residual(gain-np.eye(len(gain))[i]*1e-5))/(2e-5) for i in range(len(gain))])
        assert np.max(abs(jacobian(gain)-numerical))<2e-7
        fitted,diagnostic=calibrate(known,targets,.16)
        assert diagnostic['qualified']
        try:calibrate(known,targets*0,.16)
        except ValueError:pass
        else:raise AssertionError('Zero target admitted')
        renderer=Renderer(repo);c_errors=[]
        for seed in (*TRAIN_SEEDS,*HELD_OUT_SEEDS):
            actual,_=renderer.render(fitted,'afterfire',controls(dict(seed=seed,seconds=.2)))
            expected=synth(fitted,seed=seed);error=float(np.max(abs(actual[:len(expected)]-expected)))
            assert error<2e-6 and not actual[len(expected):].any();c_errors.append(error)
        report['known']=dict(quadratic_power_max_error=float(np.max(abs(predicted-direct))),
            jacobian_max_error=float(np.max(abs(jacobian(gain)-numerical))),known_feasible_fit=True,
            actual_C_max_error=max(c_errors),all_eight_seeds=True,zero_target_refused=True)
        print('Known finite powers/Jacobian/actual C passed',flush=True)
        cases=[]
        old_root=data/'references/analysis/short_event_scan_v1/B-fits2'
        for row in load(old_root/'report.json')['selection']:
            if row['rank'] not in (3,6):continue
            project=load(old_root/'projects'/row['project']/'project.json')
            cases.append(('B_rank'+str(row['rank']),project['document']['source_job']))
        for name in ('A_crank','A_catch'):cases.append((name,load(repo/'examples/event_authoring'/f'{name}.job.json')))
        results=[]
        for name,job in cases:
            folder=out/name;folder.mkdir();save(folder/'source-job.json',job)
            x,_,provenance=read(job['source'],*job['seconds']);bg,_,background=read(job['source'],*job['background_seconds'])
            observation,arrays=observe(x,bg);duration=len(x)/48000
            profile,_=fit(observation,arrays,duration,job.get('gated',False))
            fitted,details=search(profile,arrays,duration)
            save(folder/'profile.json',fitted);save(folder/'fit.json',details)
            sf.write(folder/'reference.wav',x,48000,subtype='FLOAT')
            seeds=[]
            for seed in (*TRAIN_SEEDS,*HELD_OUT_SEEDS):
                actual,_=renderer.render(fitted,job['kind'],controls(dict(seed=seed,seconds=max(.2,duration))))
                sf.write(folder/f'C-{seed}.wav',actual,48000,subtype='FLOAT')
                expected=synth(fitted,seed=seed,seconds=duration)
                error=float(np.max(abs(actual[:len(expected)]-expected)));assert error<2e-6
                seeds.append(dict(seed=seed,C_python_error=error))
            results.append(dict(name=name,qualified=details['qualified'],training_qualified=details['training_qualified'],
                held_out_qualified=all(r['qualified'] for r in details['held_out']),source=provenance,
                background=background,noise_lowpass_hz=details['noise_lowpass_hz'],actual_C=seeds))
            print(name,details['qualified'],details['noise_lowpass_hz'],flush=True)
        report['materials']=results
        # No edits to the old single-realization estimator; verify against frozen executed module.
        frozen=data/'baselines/short_event_authoring_v1/delivery1/repo/tools/event_authoring/response_fit.py'
        spec=importlib.util.spec_from_file_location('event_authoring.frozen_response',frozen)
        old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
        # Last case is existing A_catch; same arrays/profile and default seed.
        a,ar=response_fit.search(profile,arrays,duration);b,br=old.search(profile,arrays,duration)
        assert a==b and ar==br
        old_map=load(data/'references/analysis/short_event_scan_v1/runtime.json')
        assert len(old_map)==459 and all(sha(repo/name)==value for name,value in old_map.items())
        report.update(result='passed',legacy_single_fit_exact=True,runtime_files_unchanged=459,
                      global_event_bank_changed=False,physical_afterfire_confirmed=False)
    except Exception as error:
        report.update(result='failed',error=repr(error));raise
    finally:save(out/'report.json',report)
    print(dict(result=report['result'],output=str(out)),flush=True)


if __name__=='__main__':main()
