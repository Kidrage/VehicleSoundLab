"""Native startup configuration, original-V3 oracle, identity and replay checks."""
import argparse
from copy import deepcopy
import ctypes as C
import hashlib
import json
from pathlib import Path
import sys
import traceback

from vehicle_controller.native import Bridge,Engine,Control,Telemetry,EventNotice,pack,unpack
from vehicle_controller import startup,take,recipe
from vehicle_scenarios.capture import replay


class Legacy:
    """Call the preserved V3 binary directly, without compiling a new oracle."""
    def __init__(self,path):
        self.lib=C.CDLL(str(path))
        for key,args,result in (
            ('abi',[],C.c_uint),('control_size',[],C.c_uint),('telemetry_size',[],C.c_uint),
            ('open',[C.c_int],C.c_void_p),('close',[C.c_void_p],None),
            ('set',[C.c_void_p,C.POINTER(Control)],C.c_int),
            ('process',[C.c_void_p,C.POINTER(C.c_float),C.POINTER(C.c_float),C.c_uint],C.c_int),
            ('state',[C.c_void_p,C.POINTER(Telemetry)],C.c_int),
            ('events',[C.c_void_p,C.POINTER(EventNotice),C.c_uint],C.c_uint)):
            function=getattr(self.lib,'vsl_source_'+key);function.argtypes=args;function.restype=result
            setattr(self,key,function)
        assert self.abi()==4 and self.control_size()==C.sizeof(Control) and self.telemetry_size()==C.sizeof(Telemetry)


def assert_refused(callback):
    try:callback()
    except (ValueError,TypeError):return
    raise AssertionError('Invalid configuration was accepted')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    from startup_response_evidence_v1 import capture,verify
    binding=capture(repo,a.output);bridge=Bridge(repo)
    old_path=repo/'build-vehicle-source-v3/bin/Release/vsl_source_bridge.dll'
    old_hash=hashlib.sha256(old_path.read_bytes()).hexdigest()
    assert old_hash=='445af3ac7bc4f7236c7e29ec3a0d928503d91b59035a3a688a32c6af3a1dabe8'
    legacy=Legacy(old_path);defaults=deepcopy(bridge.startup_defaults)
    assert list(defaults.values())==[.28,220.,.07,.20,.45,1150.,.06,.55,.12]
    report=dict(schema='vsl.startup-response-verification/1',goal_complete=False,timbre_accepted=False,
        bridge_sha256=bridge.sha256,voices_sha256=bridge.voices_sha256,old_bridge_sha256=old_hash,
        defaults=defaults,abi=bridge.abi(),startup_size=C.sizeof(startup.Response))
    # Independent original binary, all catalog recipes, startup and idle/playback.
    exact=[]
    for row in bridge.catalog:
        control=bridge.initial(row['id'])[0]
        control.update(mode=1,ignition=0,start_id=0,gear=0,throttle=0.,brake=.5)
        control['events']['enabled']=1
        handle=legacy.open(row['id']);assert handle
        mix=(C.c_float*2048)();stems=(C.c_float*(1024*bridge.channels()))();notices=(EventNotice*128)()
        digest=hashlib.sha256();count=0
        try:
            with Engine(bridge,row['id']) as engine:
                for block in range(320):
                    if block==20:control.update(ignition=1,start_id=1)
                    if block==160:control.update(throttle=.4,brake=0.)
                    if block==245:control.update(throttle=0.)
                    if block==275:control.update(ignition=0)
                    native=pack(control);assert legacy.set(handle,C.byref(native));engine.set(control)
                    assert legacy.process(handle,mix,stems,480)
                    pcm=engine.process(480);assert pcm==C.string_at(mix,480*8),(row,block,'mix')
                    assert C.string_at(engine.stems,480*bridge.channels()*4)==C.string_at(stems,480*bridge.channels()*4),(row,block,'stems')
                    state=Telemetry();assert legacy.state(handle,C.byref(state));assert engine.state()==unpack(state),(row,block,'state')
                    n=legacy.events(handle,notices,128)
                    assert engine.last_events==[unpack(notices[k]) for k in range(n)],(row,block,'notice')
                    count+=n;digest.update(pcm)
        finally:legacy.close(handle)
        exact.append(dict(catalog=row['key'],frames=153600,pcm_sha256=digest.hexdigest(),notices=count))
        print(json.dumps(dict(original_v3_exact=row['key'])),flush=True)
    report['original_v3_exact']=exact
    # C and Python both reject each non-finite and out-of-range field.
    refusals=0
    with Engine(bridge,0) as engine:
        for key,_,low,high in startup.FIELDS:
            for bad in (float('nan'),float('inf'),low-.001,high+.001):
                value=deepcopy(defaults);value[key]=bad
                assert_refused(lambda:startup.validate(value))
                native=startup.Response(**value);assert not bridge.startup_set(engine.handle,C.byref(native));refusals+=1
        value=deepcopy(defaults);value['combustion_seconds']=1.5
        assert_refused(lambda:startup.validate(value));native=startup.Response(**value)
        assert not bridge.startup_set(engine.handle,C.byref(native));refusals+=1
        assert_refused(lambda:startup.validate({}));assert_refused(lambda:startup.validate(dict(defaults,flare_rpm=True)))
        response=startup.Response();assert bridge.startup_get(engine.handle,C.byref(response))
        assert unpack(response)==defaults
    custom=dict(defaults,crank_seconds=.5,catch_rise_seconds=.35,catch_settle_seconds=.8,
                flare_rpm=2000.,combustion_seconds=.1,stopping_seconds=.8,stopping_tau=.15)
    with Engine(bridge,0,startup_response=custom) as first,Engine(bridge,0) as second:
        native=startup.Response(**custom);assert bridge.startup_set(first.handle,C.byref(native))
        native.flare_rpm=2200. # Must not mutate the copied native configuration.
        response=startup.Response();assert bridge.startup_get(first.handle,C.byref(response));assert unpack(response)==custom
        assert not bridge.startup_set(None,C.byref(response)) and not bridge.startup_set(first.handle,None)
        assert not bridge.startup_get(None,C.byref(response)) and not bridge.startup_get(first.handle,None)
        assert bridge.startup_get(second.handle,C.byref(response));assert unpack(response)==defaults
        control=deepcopy(first.controls);control['events'].update(enabled=1,manual_type=1,manual_sequence=1)
        first.set(control);assert not bridge.startup_set(first.handle,C.byref(response)),'Queued event must lock configuration'
        second.process(1);assert not bridge.startup_set(second.handle,C.byref(response)),'Any processed sample must lock configuration'
    # Actual custom lifecycle, cancellation/restart, same clock, recipe and take.
    control=bridge.initial(0)[0];control.update(mode=1,ignition=1,start_id=1,gear=0,throttle=0.,brake=.7)
    control['events']['enabled']=1
    value=take.create(bridge,0,control,startup_response=custom);value['frames']=48000*8
    for seconds,changes in ((2.3,dict(ignition=0)),(2.6,dict(ignition=1,start_id=2)),
                            (3.5,dict(ignition=1,start_id=3)),(3.7,dict(ignition=0)),
                            (4.8,dict(ignition=1,start_id=4)),(6.5,dict(ignition=0))):
        control.update(changes);take.append(value,round(seconds*48000),control)
    digest=hashlib.sha256();rows=[];notices=[];index=0;pieces=[]
    with Engine(bridge,0,startup_response=custom) as engine:
        engine.set(value['initial'])
        while engine.frame<value['frames']:
            pcm,index=take.replay_block(engine,value,index,240)
            pieces.append(pcm);digest.update(pcm);notices.extend(engine.last_events)
            state=engine.state();assert state['frame']==engine.frame;rows.append(state)
    value['source_events']=notices
    # First start: .5s crank + .35s rise + .8s settle = 1.65s before RUNNING.
    states=[(row['frame']/48000,row['lifecycle']) for row in rows]
    transitions=[];previous=None
    for seconds,state in states:
        if state!=previous:transitions.append([seconds,state]);previous=state
    assert abs(transitions[1][0]-.505)<.006 and abs(transitions[2][0]-1.655)<.006,transitions
    first_rows=[row for row in rows if row['frame']<=2.3*48000]
    peak=max(row['rpm'] for row in first_rows);assert abs(peak-2000)<1e-8
    assert sum(state==2 for _,state in transitions)==3,transitions
    first_deltas=[abs(b['rpm']-a['rpm']) for a,b in zip(first_rows,first_rows[1:])]
    assert max(first_deltas)<65,max(first_deltas)
    assert rows[-1]['event_overflow']==rows[-1]['event_log_lost']==0
    assert rows[-1]['lifecycle']==0 and rows[-1]['rpm']==0
    expected=digest.hexdigest()
    replayed=replay(bridge,value);assert replayed['pcm_sha256']==expected and replayed['source_events']==notices
    take.save(a.output/'custom.vsltake.json',value);assert take.read(a.output/'custom.vsltake.json',bridge)==value
    for mutation in ('flare_rpm','missing'):
        bad=deepcopy(value)
        if mutation=='missing':del bad['startup_response']
        else:bad['startup_response'][mutation]=2100.
        take.save(a.output/(mutation+'.rejected.json'),bad)
        assert_refused(lambda:take.read(a.output/(mutation+'.rejected.json'),bridge))
    preset=recipe.create(bridge,0,value['initial'],'踏板驾驶',{},custom);recipe.validate(bridge,preset)
    bad=deepcopy(preset);bad['startup_response']['flare_rpm']=2100.
    assert_refused(lambda:recipe.validate(bridge,bad))
    take.save(a.output/'custom.preset.json',preset)
    from vehicle_controller.render import FloatWav,export
    writer=FloatWav(a.output/'custom.wav',2)
    try:
        for pcm in pieces:writer.write(pcm)
    finally:writer.close()
    rendered=export(bridge,value,a.output/'export'/'custom',stems=False)
    assert (a.output/'custom.wav').read_bytes()==(a.output/'export'/'custom_mix.wav').read_bytes()
    report.update(result='passed',invalid_native_and_python_refusals=refusals,
        instance_isolation=True,copy_semantics=True,preframe_and_empty_queue_required=True,
        custom_response=custom,custom_peak_rpm=peak,max_first_start_rpm_step=max(first_deltas),
        transitions=transitions,custom_pcm_sha256=expected,custom_frames=value['frames'],
        exact_variable_block_replay=True,notices=notices,final_state=rows[-1],
        preset_take_tamper_refused=True,native_export_exact=True)
    verify(repo,binding);report['source_binding_sha256']=hashlib.sha256((a.output/'source_binding.json').read_bytes()).hexdigest()
    take.save(a.output/'telemetry.json',rows);take.save(a.output/'report.json',report)
    print(json.dumps(dict(result='passed',default_presets=len(exact),peak=peak,transitions=transitions)),flush=True)


if __name__=='__main__':
    try:main()
    except Exception:
        if '--output' in sys.argv:
            folder=Path(sys.argv[sys.argv.index('--output')+1]);folder.mkdir(parents=True,exist_ok=True)
            (folder/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
