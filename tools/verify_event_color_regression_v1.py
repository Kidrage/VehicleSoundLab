"""Compare actual V6 to preserved V5 across every catalog and startup abort edges."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil

import numpy as np

from vehicle_controller.native import Bridge,Engine
from startup_response_evidence_v1 import capture,verify,sha


def render(bridge,selection,control,changes,frames):
    mix=[];native=[];states=[];notices=[];index=0
    with Engine(bridge,selection) as engine:
        engine.set(control)
        while engine.frame<frames:
            if index<len(changes) and engine.frame==changes[index][0]:
                control=deepcopy(control);control.update(changes[index][1]);engine.set(control);index+=1
            count=min(480,frames-engine.frame,changes[index][0]-engine.frame if index<len(changes) else frames)
            mix.append(engine.process(count))
            native.append(np.ctypeslib.as_array(engine.stems)[:count*bridge.channels()].copy())
            states.append(engine.state());notices.extend(engine.last_events)
    return b''.join(mix),np.concatenate(native),states,notices


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);repo=Path(__file__).resolve().parents[1]
    current=Bridge(repo);old=Bridge(repo,repo/'build-vehicle-source-v5/bin/Release/vsl_source_bridge.dll')
    assert old.sha256=='39496f215967a1b6449fab7d9841961d12a74d368d2e5afc8dade701e5ed0d43'
    binding=capture(repo,a.output,current.path);shutil.copy2(__file__,a.output/'executed_verification.py');cases=[]
    def check(selection,control,changes,frames,label):
        x=render(old,selection,deepcopy(control),changes,frames)
        y=render(current,selection,deepcopy(control),changes,frames)
        assert x[0]==y[0] and np.array_equal(x[1],y[1]) and x[2:]==y[2:],label
        cases.append(dict(catalog=selection,label=label,frames=frames,mix_native_state_notices_exact=True))
    for row in current.catalog:
        for enabled in (0,1):
            c=current.initial(row['id'])[0];c.update(mode=1,ignition=0,start_id=0,gear=0,automatic=0,throttle=0.,brake=.7)
            c['events']['enabled']=enabled
            check(row['id'],c,[(10013,dict(ignition=1,start_id=1)),(80017,dict(throttle=.35)),
                              (120019,dict(ignition=0,throttle=0.))],153600,'normal/events='+str(enabled))
        print(json.dumps(dict(passed_catalog=row['key'])),flush=True)
    for frame,decay in ((7200,1.),(21600,1.),(21733,4.)):
        c=current.initial(1)[0];c.update(mode=1,ignition=1,start_id=1,gear=0,automatic=0,throttle=0.,brake=.7)
        c['events'].update(enabled=1,decay=decay)
        check(1,c,[(frame,dict(ignition=0))],192000,'abort/'+str(frame))
    verify(repo,binding)
    report=dict(schema='vsl.event-color-regression/1',result='passed',cases=cases,bridge_sha256=current.sha256,
        reference_bridge_sha256=old.sha256,abi=[current.abi(),old.abi()],source_binding_sha256=sha(a.output/'source_binding.json'),
        timbre_accepted=False,goal_complete=False)
    (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(result='passed',cases=len(cases))))


if __name__=='__main__':main()
