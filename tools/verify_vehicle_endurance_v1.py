"""Repeated full cycles in one C engine without resetting voices or the clock."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--cycles',type=int,default=10);a=p.parse_args()
    if not 2<=a.cycles<=100:raise ValueError('Use 2–100 bounded cycles')
    a.output.mkdir(parents=True,exist_ok=False);sys.path.insert(0,'E:/VehicleSoundLab/tools/python_deps')
    import numpy as np
    from vehicle_controller.native import Bridge,Engine
    from vehicle_controller import take
    from vehicle_scenarios.scenario import sport_lifecycle
    repo=Path(__file__).resolve().parents[1]
    for relative in ('tools/verify_vehicle_endurance_v1.py','tools/vehicle_scenarios/scenario.py',
                     'tools/vehicle_controller/native.py','tools/vehicle_controller/take.py'):
        path=a.output/'exact_sources'/relative;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/relative,path)
    bridge=Bridge(repo);base,scenario=sport_lifecycle(bridge);combined=deepcopy(base)
    combined['events']=[];combined['source_events']=[];rows=[];identities=set();active={}
    digest=hashlib.sha256();peak=0.;started=time.perf_counter()
    try:
        with Engine(bridge,0) as engine:
            previous_overruns=previous_shifts=0
            for cycle in range(a.cycles):
                origin=engine.frame;control=deepcopy(base['initial']);control['start_id']=cycle
                engine.set(control)
                if origin:take.append(combined,origin,control)
                changes=deepcopy(base['events'])
                for event in changes:event['frame']+=origin;event['control']['start_id']+=cycle
                index=0;notices=[];life=set();operating=set();cycle_peak=0.
                while engine.frame<origin+base['frames']:
                    while index<len(changes) and engine.frame==changes[index]['frame']:
                        engine.set(changes[index]['control']);take.append(combined,engine.frame,engine.controls);index+=1
                    end=min(engine.frame+960,origin+base['frames'],changes[index]['frame'] if index<len(changes) else origin+base['frames'])
                    data=engine.process(end-engine.frame);x=np.frombuffer(data,dtype='<f4')
                    assert np.isfinite(x).all()
                    digest.update(data);cycle_peak=max(cycle_peak,float(np.max(abs(x))))
                    notices.extend(engine.last_events);combined['source_events'].extend(engine.last_events)
                    state=engine.state();life.add(state['lifecycle']);operating.add(state['operating'])
                    assert 0<=state['rpm']<=10000 and state['speed_mps']>=0
                    assert state['event_active']<=4 and state['event_overflow']==state['event_log_lost']==0
                    for e in engine.last_events:
                        if e['action']==1:
                            assert e['id'] not in identities and e['slot'] not in active
                            identities.add(e['id']);active[e['slot']]=e['id']
                        elif e['action']==2:assert active.pop(e['slot'],None)==e['id']
                        else:raise AssertionError('Event rejected: '+str(e))
                state=engine.state();starts=[n for n in notices if n['action']==1]
                assert [n['type'] for n in starts]==[1,2] and not active
                assert state['lifecycle']==0 and state['speed_mps']<.02 and state['event_active']==state['event_queue']==0
                assert state['overruns']>previous_overruns and state['shifts']>=previous_shifts+2
                assert all(k in life for k in (0,2,3,4,5)) and all(k in operating for k in (0,2,4,5,6,7))
                assert cycle_peak<1
                previous_overruns=state['overruns'];previous_shifts=state['shifts'];peak=max(peak,cycle_peak)
                rows.append(dict(cycle=cycle+1,first_frame=origin,last_frame=engine.frame,peak=cycle_peak,
                    event_ids=[e['id'] for e in starts],final_state=state,notices=notices,
                    lifecycle_states=sorted(life),operating_states=sorted(operating)))
                print(json.dumps(dict(cycle=cycle+1,generated_seconds=engine.frame/48000,
                    unique_event_ids=len(identities),shifts=state['shifts'],overruns=state['overruns'])),flush=True)
    finally:
        combined['frames']=rows[-1]['last_frame'] if rows else 0
        take.save(a.output/'endurance.vsltake.json',combined)
        (a.output/'cycles.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    report=dict(schema='vsl.vehicle-endurance-verification/1',result='passed',cycles=a.cycles,
        generated_seconds=combined['frames']/48000,one_engine_instance=True,clock_reset=False,
        bridge_sha256=bridge.sha256,voices_sha256=bridge.voices_sha256,event_bank_sha256=bridge.event_bank_sha256,
        pcm_sha256=digest.hexdigest(),peak=peak,unique_event_ids=len(identities),event_notices=len(combined['source_events']),
        wall_seconds=time.perf_counter()-started,final_state=rows[-1]['final_state'],
        timbre_accepted=False,goal_complete=False,
        limits=['Offline native generation; not a real-time device, target-board or soak qualification.',
                'Missing event types remain silent; this does not exercise real afterfire/shift timbres.'])
    (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':
    try:main()
    except Exception:
        import traceback
        if '--output' in sys.argv:
            folder=Path(sys.argv[sys.argv.index('--output')+1]);folder.mkdir(parents=True,exist_ok=True)
            (folder/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
