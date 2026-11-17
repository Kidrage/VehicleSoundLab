"""Actual old/new C, source ownership, multi-stage envelopes and full startup replay."""
import argparse
from copy import deepcopy
import ctypes as ct
import json
from pathlib import Path
import shutil
import numpy as np
import soundfile as sf
from event_authoring.audio import sha
from event_authoring.contract import Profile,ProfileV1,ProfileV2,ProfileV3,Request,pack_profile,KINDS,validate
from event_authoring.model import synth
from event_authoring.native import Renderer
from event_designer.package import write_json
from vehicle_controller.native import Bridge
from vehicle_controller import recipe
from startup_handoff_v1.session import generate
from startup_response_evidence_v1 import capture as bind,verify


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];root=Path('E:/VehicleSoundLab/references/analysis/startup_contour_v1')
    renderer=Renderer(repo);oldpath=repo/'build-event-synth-v3/bin/Release/vsl_event_author_bridge.dll'
    oldlib=ct.CDLL(str(oldpath));oldfn=oldlib.vsl_event_author_render
    oldfn.argtypes=[ct.POINTER(ProfileV3),ct.POINTER(Request),ct.c_uint,ct.c_uint,ct.POINTER(ct.c_float)];oldfn.restype=ct.c_int
    assert (ct.sizeof(ProfileV1),ct.sizeof(ProfileV2),ct.sizeof(ProfileV3),ct.sizeof(Profile))==(696,704,800,1408)
    source=json.loads(Path('E:/VehicleSoundLab/references/analysis/startup_shape_v1/verification2/V11-candidate/startup.recipe.json').read_text(encoding='utf-8'))
    profiles=[(k,d['parameters']) for k,d in source['event_overrides'].items()]
    fixture=dict(gated=0,duration_seconds=.7,attack_seconds=.006,release_seconds=.025,sweep_seconds=.2,level=.2,
        modes=[dict(hz=97.,end_hz=140.,amplitude=.1,phase=.3,decay_seconds=.21),
               dict(hz=1577.,end_hz=1777.,amplitude=.04,phase=-.3,decay_seconds=.34)],
        bands=[dict(hz=2200.,q=.8,amplitude=.02,attack_seconds=.02,decay_seconds=.15)],noise_lowpass_hz=6000.)
    profiles += [(k,dict(deepcopy(fixture),gated=i%2)) for i,k in enumerate(KINDS)]
    profiles.append(('catch',deepcopy(source['event_overrides']['catch']['parameters'])))
    exact=[]
    for kind,p in profiles:
        for seed,pitch,decay in ((27431,1.,1.),(48271,.7,.6),(93931,1.3,1.4)):
            values=dict(seconds=1.2,seed=seed,pitch=pitch,decay=decay,hold_seconds=.4)
            current,_=renderer.render(p,kind,values);previous=np.zeros(len(current),dtype='float32')
            native=pack_profile(p,ProfileV3)
            req=Request(id=1,type=KINDS.index(kind),priority=100,seed=seed,strength=1.,pitch=pitch,decay=decay,texture=1.)
            release=19200 if p['gated'] else 0xffffffff
            assert oldfn(ct.byref(native),ct.byref(req),len(previous),release,previous.ctypes.data_as(ct.POINTER(ct.c_float)))
            assert np.array_equal(previous,current),(kind,values)
            exact.append(dict(kind=kind,seed=seed,pitch=pitch,decay=decay,exact=True))
    print(json.dumps(dict(legacy_author_cases=len(exact),result='passed')),flush=True)
    candidate=json.loads((root/'candidate1/analysis/profile.json').read_text(encoding='utf-8'))
    invalid=[]
    for key,value in [('gain',[-.1]*8),('gain',[9.]*8),('gain',[float('nan')]*8),
                      ('seconds',[0,0,.1,.2,.3,.4,.5,.8]),('seconds',[.01,.1]),('gain',[1.]),('low_hz',4500)]:
        p=deepcopy(candidate['parameters']);p['contours'][0][key]=value
        try:validate(p)
        except ValueError:invalid.append(key+':'+str(value))
        else:raise AssertionError((key,value))
    p=deepcopy(candidate['parameters']);p['contours'].append(deepcopy(p['contours'][0]))
    try:validate(p)
    except ValueError:invalid.append('overlap')
    else:raise AssertionError('overlap')
    for cls in (ProfileV1,ProfileV2,ProfileV3):
        try:pack_profile(candidate['parameters'],cls)
        except ValueError:pass
        else:raise AssertionError('old profile silently dropped contours')
    comparisons=[]
    for gated in (0,1):
      for cutoff in (0,6000):
        p=deepcopy(fixture);p['gated']=gated;p['noise_lowpass_hz']=cutoff
        p['modes'][0]['attack_seconds']=.34;p['modes'][1]['attack_seconds']=.012
        p['contours']=[dict(low_hz=1000,high_hz=3000,seconds=[0,.03,.12,.25,.4],gain=[.1,1,.05,.7,.3])]
        for seed,pitch,decay in ((27431,1.,1.),(48271,.5,.6),(93931,2.,1.4)):
            values=dict(seconds=1.2,seed=seed,pitch=pitch,decay=decay,hold_seconds=.4,texture=1.3,strength=.7)
            actual,_=renderer.render(p,'catch',values)
            other=synth(p,seed=seed,pitch=pitch,decay=decay,seconds=1.2,texture=1.3,strength=.7,release_at=.4 if gated else None)
            other=np.pad(other,(0,len(actual)-len(other)))
            error=float(np.max(abs(actual-other)));assert error<3e-7,error
            comparisons.append(dict(gated=gated,cutoff=cutoff,seed=seed,pitch=pitch,decay=decay,max_error=error))
    for seed in (27431,48271,93931,17389):
        folder=out/str(seed);folder.mkdir()
        actual,report=renderer.render(candidate['parameters'],'catch',dict(seconds=1.2,seed=seed))
        sf.write(folder/'synthesis.wav',actual,48000,subtype='FLOAT');write_json(folder/'report.json',report)
        other=synth(candidate['parameters'],seed=seed,seconds=1.2);other=np.pad(other,(0,len(actual)-len(other)))
        assert np.max(abs(actual-other))<3e-7
    current=Bridge(repo);previous=Bridge(repo,repo/'build-vehicle-source-v11/bin/Release/vsl_source_bridge.dll')
    assert (current.abi(),previous.abi())==(11,10)
    assert previous.sha256=='3e7b7e9d837bdf14a6cc28678e5358e00a3438556e917877d187f4b854982460'
    binding=bind(repo,out,current.path)
    old=generate(previous,source,out/'V11-original',crank_seconds=.58)
    zero=generate(current,source,out/'V12-original',crank_seconds=.58)
    x,_=sf.read(out/'V11-original/native.wav',dtype='float32',always_2d=True)
    y,_=sf.read(out/'V12-original/native.wav',dtype='float32',always_2d=True)
    assert np.array_equal(x,y) and old['pcm_sha256']==zero['pcm_sha256']
    assert old['final_state']==zero['final_state']
    original_source=deepcopy(source);source['event_overrides']['catch']=candidate
    changed=generate(current,source,out/'V12-candidate',crank_seconds=.58)
    z,_=sf.read(out/'V12-candidate/native.wav',dtype='float32',always_2d=True)
    assert np.array_equal(y[:,:19],z[:,:19]) and not np.array_equal(y[:,19:],z[:,19:])
    assert changed['final_state']==zero['final_state']
    original_take=json.loads((out/'V12-original/lifecycle.vsltake.json').read_text(encoding='utf-8'))
    new_take=json.loads((out/'V12-candidate/lifecycle.vsltake.json').read_text(encoding='utf-8'))
    assert original_take['source_events']==new_take['source_events']
    try:recipe.validate(current,json.loads((out/'V11-original/startup.recipe.json').read_text(encoding='utf-8')))
    except ValueError:pass
    else:raise AssertionError('old binary recipe migrated silently')
    frozen=Path('E:/VehicleSoundLab/baselines/startup_shape_v1/delivery1/evidence/verification2/exact_sources')
    voices=sorted((repo/'voices').rglob('*'));voices=[p for p in voices if p.is_file()]
    assert len(voices)==89 and all(sha(p)==sha(frozen/p.relative_to(repo)) for p in voices)
    runtime=[p for folder in ('modules','src') for p in (repo/folder).rglob('*') if p.suffix in ('.c','.h')]
    changes=[p.relative_to(repo).as_posix() for p in runtime if not (frozen/p.relative_to(repo)).is_file() or sha(p)!=sha(frozen/p.relative_to(repo))]
    assert set(changes)=={'modules/event_synth/api.h','modules/event_synth/voice.c','modules/event_synth/profile.c',
                         'modules/event_synth/contour.c','modules/event_synth/internal.h'},changes
    verify(repo,binding)
    write_json(out/'report.json',dict(result='passed',author_legacy_exact=exact,independent_model=comparisons,
        invalid_contours_refused=invalid,old_layout_nonzero_refused=True,original_startup_23channels_exact=True,
        candidate_continuous_19channels_exact=True,only_candidate_event_audio_changes=True,
        event_notices_and_driver_final_state_exact=True,variable_block_replays_exact=True,
        old_recipe_refused=True,current_bridge_sha256=current.sha256,old_bridge_sha256=previous.sha256,
        author_bridge_sha256=renderer.identity,old_author_sha256=sha(oldpath),runtime_changes=changes,
        formal_voices_unchanged=len(voices),source_binding_verified=True,timbre_accepted=False,goal_complete=False))
    shutil.copy2(__file__,out/'executed_verification.py')
    print(json.dumps(dict(result='passed',output=str(out),bridge=current.sha256)),flush=True)


if __name__=='__main__':main()
