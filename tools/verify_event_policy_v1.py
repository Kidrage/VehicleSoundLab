"""Actual V7 recipe, preserved-V6 audio, native timing and replay verification."""
import argparse
from copy import deepcopy
import ctypes as C
import hashlib
import json
from pathlib import Path
import shutil
import traceback

import numpy as np

from vehicle_controller.native import Bridge,Engine,unpack
from vehicle_controller import event_policy as policy,recipe,take
from vehicle_controller.render import export
from vehicle_scenarios.capture import replay
from startup_response_evidence_v1 import capture,verify,sha


def refused(call):
    try:call()
    except (ValueError,TypeError):return
    raise AssertionError('Invalid configuration accepted')


def generate(bridge,selection,control,changes,frames,overrides=None,configuration=None,blocks=(480,)):
    mix=[];native=[];states=[];notices=[];stats=[];index=0;block=0
    with Engine(bridge,selection,overrides,event_policy=configuration) as engine:
        engine.set(control)
        while engine.frame<frames:
            while index<len(changes) and changes[index][0]==engine.frame:
                change=changes[index][1];control=deepcopy(control)
                for key,value in change.items():
                    if key=='events':control[key].update(value)
                    else:control[key]=value
                engine.set(control);index+=1
            count=min(blocks[block%len(blocks)],frames-engine.frame,
                changes[index][0]-engine.frame if index<len(changes) else frames)
            mix.append(engine.process(count))
            native.append(np.ctypeslib.as_array(engine.stems)[:count*bridge.channels()].copy().reshape(count,-1))
            states.append(engine.state());notices.extend(engine.last_events);stats.append(engine.policy_stats());block+=1
    return dict(pcm=b''.join(mix),native=np.concatenate(native),states=states,notices=notices,stats=stats)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);repo=Path(__file__).resolve().parents[1]
    bridge=Bridge(repo);old=Bridge(repo,repo/'build-vehicle-source-v6/bin/Release/vsl_source_bridge.dll')
    assert bridge.abi()==7 and old.abi()==6
    assert old.sha256=='d6e383857365705bc60f6f4a4271c1c5a1793c0e3b485b4fb5a342dd990ebeb4'
    binding=capture(repo,a.output,bridge.path);shutil.copy2(__file__,a.output/'executed_verification.py')
    assert C.sizeof(policy.Policy)==72 and C.sizeof(policy.Stats)==20
    assert bridge.event_policy_defaults==policy.defaults();cases=[]
    def check(selection,control,changes,frames,label,overrides=None):
        x=generate(old,selection,deepcopy(control),changes,frames,overrides)
        y=generate(bridge,selection,deepcopy(control),changes,frames,overrides)
        assert x['pcm']==y['pcm'] and np.array_equal(x['native'],y['native']),label
        assert x['states']==y['states'] and x['notices']==y['notices'],label
        cases.append(dict(catalog=selection,label=label,frames=frames,notices=len(y['notices']),
            exact_mix_stems_states_notices=True,pcm_sha256=hashlib.sha256(y['pcm']).hexdigest()))
        return y
    for row in bridge.catalog:
        for enabled in (0,1):
            c=bridge.initial(row['id'])[0];c.update(mode=1,ignition=0,start_id=0,gear=0,automatic=0,throttle=0.,brake=.7)
            c['events']['enabled']=enabled
            check(row['id'],c,[(10013,dict(ignition=1,start_id=1)),(80017,dict(throttle=.35)),
                (120019,dict(ignition=0,throttle=0.))],153600,'normal/events='+str(enabled))
        print(json.dumps(dict(default_exact_catalog=row['key'])),flush=True)
    for frame,decay in ((7200,1.),(21600,1.),(21733,4.)):
        c=bridge.initial(1)[0];c.update(mode=1,ignition=1,start_id=1,gear=0,automatic=0,throttle=0.,brake=.7)
        c['events'].update(enabled=1,decay=decay)
        check(1,c,[(frame,dict(ignition=0))],192000,'abort/'+str(frame))
    # Existing approved-source scoped candidate is a local engineering slot,
    # never evidence of physical afterfire or promotion to the formal bank.
    source=Path('E:/VehicleSoundLab/designs/events/028a56d636574ab1bb902a1d3479ac7e/project.json')
    overrides={'afterfire':json.loads(source.read_text(encoding='utf-8'))['document']}
    c=bridge.initial(0)[0];c.update(mode=1,ignition=1,start_id=1,gear=0,automatic=0,throttle=.85,brake=0.)
    c['events']['enabled']=1
    changes=[(192000,dict(throttle=0.)),(240000,dict(throttle=.85)),(312000,dict(throttle=0.))]
    baseline=check(0,c,changes,432000,'two-qualified-lifts/local-E-slot',overrides)
    assert baseline['stats'][-1]['opportunities']==2
    default_starts=[n for n in baseline['notices'] if n['type']==3 and n['action']==1]
    assert default_starts
    custom=dict(bridge.event_policy_defaults,afterfire_min_count=3,afterfire_max_count=3,
        afterfire_delay_seconds=.04,afterfire_interval_min_seconds=.12,afterfire_interval_max_seconds=.12,
        afterfire_repeat_gain=.5,afterfire_cooldown_seconds=3.)
    y=generate(bridge,0,deepcopy(c),changes,432000,overrides,custom)
    starts=[n for n in y['notices'] if n['type']==3 and n['action']==1]
    assert len(starts)==3 and [n['requested_frame'] for n in starts]==[196320,202080,207840],starts
    assert y['stats'][-1]==dict(opportunities=2,bursts_attempted=1,unavailable=0,probability_skips=0,cooldown_skips=1)
    assert np.array_equal(baseline['native'][:,:19],y['native'][:,:19]),'Policy changed continuous sources'
    zero=dict(custom,afterfire_probability=0.)
    manual=changes+[(350000,dict(events=dict(manual_type=3,manual_sequence=1)))]
    z=generate(bridge,0,deepcopy(c),manual,432000,overrides,zero)
    zs=[n for n in z['notices'] if n['type']==3 and n['action']==1]
    assert len(zs)==1 and zs[0]['frame']==350000 and z['stats'][-1]['probability_skips']==2
    missing=generate(bridge,0,deepcopy(c),changes,432000)
    assert missing['stats'][-1]['unavailable']==2 and not any(n['type']==3 for n in missing['notices'])
    # Finite/range/count checks at both public boundaries, plus instance locks.
    invalid=[]
    for key,label,lo,hi,step,default in policy.FIELDS:
        for value in (lo-1,hi+1,float('nan'),float('inf')):
            doc=dict(custom);doc[key]=value;refused(lambda:policy.validate(doc))
            if key not in ('afterfire_min_count','afterfire_max_count') or np.isfinite(value):invalid.append(doc)
    for patch in ({'afterfire_min_count':2.5},{'afterfire_probability':True},
                  {'afterfire_min_count':4,'afterfire_max_count':2},
                  {'afterfire_interval_min_seconds':.3,'afterfire_interval_max_seconds':.2}):
        refused(lambda:policy.validate(dict(custom,**patch)))
    with Engine(bridge,0,event_policy=custom) as first,Engine(bridge,0) as second:
        for bad in invalid:
            native=policy.Policy(**bad);assert not bridge.event_policy_set(first.handle,C.byref(native)),bad
        native=policy.Policy(**custom);assert bridge.event_policy_set(first.handle,C.byref(native))
        native.afterfire_probability=0
        copied=policy.Policy();assert bridge.event_policy_get(first.handle,C.byref(copied));assert unpack(copied)==custom
        assert bridge.event_policy_get(second.handle,C.byref(copied));assert unpack(copied)==bridge.event_policy_defaults
        assert not bridge.event_policy_set(None,C.byref(copied)) and not bridge.event_policy_set(first.handle,None)
        first.process(1);assert not bridge.event_policy_set(first.handle,C.byref(native))
        control=deepcopy(second.controls);control['events'].update(enabled=1,manual_type=1,manual_sequence=1)
        second.set(control);assert not bridge.event_policy_set(second.handle,C.byref(native))
    refused(lambda:Engine(old,0,event_policy=custom))
    # Same document powers native generation, varied-block playback and export.
    value=take.create(bridge,0,c,overrides,event_policy=custom);value['frames']=432000
    control=deepcopy(c)
    for frame,change in changes:control.update(change);take.append(value,frame,control)
    value['source_events']=y['notices'];path=a.output/'custom.vsltake.json';take.save(path,value)
    assert take.read(path,bridge)==value
    played=replay(bridge,value);assert played['pcm_sha256']==hashlib.sha256(y['pcm']).hexdigest()
    assert played['source_events']==y['notices'] and played['final_state']==y['states'][-1]
    preset=recipe.create(bridge,0,c,'踏板驾驶',overrides,event_policy=custom);recipe.validate(bridge,preset)
    take.save(a.output/'custom.recipe.json',preset)
    for key in ('afterfire_probability','missing','schema','identity'):
        bad=deepcopy(value);other=deepcopy(preset)
        for doc in (bad,other):
            if key=='missing':del doc['event_policy']
            elif key=='schema':doc['schema']=doc['schema'].rsplit('/',1)[0]+'/'+('5' if doc is bad else '4')
            elif key=='identity':doc['source_effective_sha256']='0'*64
            else:doc['event_policy'][key]=.5
        take.save(a.output/(key+'.rejected.json'),bad);refused(lambda:take.read(a.output/(key+'.rejected.json'),bridge))
        refused(lambda:recipe.validate(bridge,other))
    # Old documents retain their old binary identity and remain playable there.
    oldvalue=take.create(old,0,c);oldvalue['frames']=480;take.save(a.output/'legacy.vsltake.json',oldvalue)
    assert take.read(a.output/'legacy.vsltake.json',old)==oldvalue
    refused(lambda:take.read(a.output/'legacy.vsltake.json',bridge))
    exported=export(bridge,value,a.output/'export/custom')
    wav=Path(exported['paths'][0]).read_bytes();assert wav[44:]==y['pcm']
    assert exported['source_events']==y['notices']
    verify(repo,binding)
    report=dict(schema='vsl.event-policy-verification/1',result='passed',default_v6_exact=cases,
        bridge_sha256=bridge.sha256,old_bridge_sha256=old.sha256,voices_sha256=bridge.voices_sha256,
        policy=custom,automatic_starts=starts,policy_stats=y['stats'][-1],probability_zero_manual_start=zs,
        missing_model_stats=missing['stats'][-1],invalid_native_cases=len(invalid),continuous_19_channels_exact=True,
        varied_block_replay_exact=True,recipe_take_tamper_refused=True,export_exact=True,
        scoped_E_physical_type_confirmed=False,goal_complete=False,timbre_accepted=False)
    take.save(a.output/'report.json',report);print(json.dumps(dict(result='passed',cases=len(cases),starts=starts)))


if __name__=='__main__':
    try:main()
    except Exception:
        import sys
        if '--output' in sys.argv:
            folder=Path(sys.argv[sys.argv.index('--output')+1]);folder.mkdir(parents=True,exist_ok=True)
            (folder/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
