"""Actual old/new C, source ownership, modal envelopes and full startup replay."""
import argparse
from copy import deepcopy
import ctypes as ct
import json
from pathlib import Path
import shutil
import numpy as np
import soundfile as sf
from event_authoring.audio import sha
from event_authoring.contract import Profile,ProfileV1,ProfileV2,Request,pack_profile,KINDS,validate
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
    repo=Path(__file__).resolve().parents[1];root=Path('E:/VehicleSoundLab/references/analysis/startup_shape_v1')
    renderer=Renderer(repo);oldpath=repo/'build-event-synth-v2/bin/Release/vsl_event_author_bridge.dll'
    oldlib=ct.CDLL(str(oldpath));oldfn=oldlib.vsl_event_author_render
    oldfn.argtypes=[ct.POINTER(ProfileV2),ct.POINTER(Request),ct.c_uint,ct.c_uint,ct.POINTER(ct.c_float)];oldfn.restype=ct.c_int
    assert (ct.sizeof(ProfileV1),ct.sizeof(ProfileV2),ct.sizeof(Profile))==(696,704,800)
    source=json.loads(Path('E:/VehicleSoundLab/references/analysis/startup_handoff_v1/fixed1/startup.recipe.json').read_text(encoding='utf-8'))
    profiles=[(k,d['parameters']) for k,d in source['event_overrides'].items()]
    fixture=dict(gated=0,duration_seconds=.7,attack_seconds=.006,release_seconds=.025,sweep_seconds=.2,level=.2,
        modes=[dict(hz=97.,end_hz=140.,amplitude=.1,phase=.3,decay_seconds=.21),
               dict(hz=1577.,end_hz=1777.,amplitude=.04,phase=-.3,decay_seconds=.34)],
        bands=[dict(hz=2200.,q=.8,amplitude=.02,attack_seconds=.02,decay_seconds=.15)],noise_lowpass_hz=6000.)
    profiles += [(k,dict(deepcopy(fixture),gated=i%2)) for i,k in enumerate(KINDS)]
    exact=[]
    for kind,p in profiles:
        for seed,pitch,decay in ((27431,1.,1.),(48271,.7,.6),(93931,1.3,1.4)):
            values=dict(seconds=1.2,seed=seed,pitch=pitch,decay=decay,hold_seconds=.4)
            current,_=renderer.render(p,kind,values);previous=np.zeros(len(current),dtype='float32')
            native=pack_profile(p,ProfileV2)
            req=Request(id=1,type=KINDS.index(kind),priority=100,seed=seed,strength=1.,pitch=pitch,decay=decay,texture=1.)
            release=19200 if p['gated'] else 0xffffffff
            assert oldfn(ct.byref(native),ct.byref(req),len(previous),release,previous.ctypes.data_as(ct.POINTER(ct.c_float)))
            assert np.array_equal(previous,current),(kind,values)
            exact.append(dict(kind=kind,seed=seed,pitch=pitch,decay=decay,exact=True))
    print(json.dumps(dict(legacy_author_cases=len(exact),result='passed')),flush=True)
    candidate=json.loads((root/'candidate2/analysis/profile.json').read_text(encoding='utf-8'))
    invalid=[]
    for value in (-.1,2.01,float('nan'),True):
        p=deepcopy(candidate['parameters']);p['modes'][0]['attack_seconds']=value
        try:validate(p)
        except ValueError:invalid.append(str(value))
        else:raise AssertionError(value)
    for cls in (ProfileV1,ProfileV2):
        try:pack_profile(candidate['parameters'],cls)
        except ValueError:pass
        else:raise AssertionError('old profile silently dropped attack')
    comparisons=[]
    for gated in (0,1):
        p=deepcopy(fixture);p['gated']=gated
        p['modes'][0]['attack_seconds']=.34;p['modes'][1]['attack_seconds']=.012
        for seed,pitch,decay in ((27431,1.,1.),(48271,.7,.6),(93931,1.3,1.4)):
            current,_=renderer.render(p,'catch',dict(seconds=1.2,seed=seed,pitch=pitch,decay=decay,hold_seconds=.4))
            other=synth(p,seed=seed,pitch=pitch,decay=decay,seconds=1.2,release_at=.4 if gated else None)
            other=np.pad(other,(0,len(current)-len(other)))
            error=float(np.max(abs(current-other)));assert error<3e-7,error
            comparisons.append(dict(gated=gated,seed=seed,pitch=pitch,decay=decay,max_error=error))
    current=Bridge(repo);previous=Bridge(repo,repo/'build-vehicle-source-v10/bin/Release/vsl_source_bridge.dll')
    assert (current.abi(),previous.abi())==(10,9)
    assert previous.sha256=='6a5a6a7323b95e09c1f8e01b7df4aff975d57b16e827a3cb7934c3cfb22d29c8'
    binding=bind(repo,out,current.path)
    old=generate(previous,source,out/'V10-original',crank_seconds=.58)
    zero=generate(current,source,out/'V11-original',crank_seconds=.58)
    x,_=sf.read(out/'V10-original/native.wav',dtype='float32',always_2d=True)
    y,_=sf.read(out/'V11-original/native.wav',dtype='float32',always_2d=True)
    assert np.array_equal(x,y) and old['pcm_sha256']==zero['pcm_sha256']
    assert old['final_state']==zero['final_state']
    original_source=deepcopy(source);source['event_overrides']['catch']=candidate
    changed=generate(current,source,out/'V11-candidate',crank_seconds=.58)
    z,_=sf.read(out/'V11-candidate/native.wav',dtype='float32',always_2d=True)
    assert np.array_equal(y[:,:19],z[:,:19]) and not np.array_equal(y[:,19:],z[:,19:])
    assert changed['final_state']==zero['final_state']
    original_take=json.loads((out/'V11-original/lifecycle.vsltake.json').read_text(encoding='utf-8'))
    new_take=json.loads((out/'V11-candidate/lifecycle.vsltake.json').read_text(encoding='utf-8'))
    assert original_take['source_events']==new_take['source_events']
    try:recipe.validate(current,json.loads((out/'V10-original/startup.recipe.json').read_text(encoding='utf-8')))
    except ValueError:pass
    else:raise AssertionError('old binary recipe migrated silently')
    before=json.loads((root/'source_before1/hashes.json').read_text(encoding='utf-8'))
    voices=[k for k in before if k.startswith('voices/')]
    assert all(sha(repo/k)==before[k] for k in voices)
    runtime=[k for k in before if k.split('/')[0] in ('modules','src') and Path(k).suffix in ('.c','.h')]
    changes=[k for k in runtime if sha(repo/k)!=before[k]]
    assert set(changes)=={'modules/event_synth/api.h','modules/event_synth/voice.c','modules/event_synth/profile.c'},changes
    verify(repo,binding)
    write_json(out/'report.json',dict(result='passed',author_legacy_exact=exact,independent_model=comparisons,
        invalid_attacks_refused=invalid,old_layout_nonzero_refused=True,original_startup_23channels_exact=True,
        candidate_continuous_19channels_exact=True,only_candidate_event_audio_changes=True,
        event_notices_and_driver_final_state_exact=True,variable_block_replays_exact=True,
        old_recipe_refused=True,current_bridge_sha256=current.sha256,old_bridge_sha256=previous.sha256,
        author_bridge_sha256=renderer.identity,old_author_sha256=sha(oldpath),runtime_changes=changes,
        formal_voices_unchanged=len(voices),source_binding_verified=True,timbre_accepted=False,goal_complete=False))
    shutil.copy2(__file__,out/'executed_verification.py')
    print(json.dumps(dict(result='passed',output=str(out),bridge=current.sha256)),flush=True)


if __name__=='__main__':main()
