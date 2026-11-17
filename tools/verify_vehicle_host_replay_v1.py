"""A synthesized control-only replay must record actual event notices once."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import time


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    for relative in ('tools/verify_vehicle_host_replay_v1.py','tools/vehicle_controller/host.py','tools/vehicle_controller/take.py'):
        path=a.output/'exact_sources'/relative;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/relative,path)
    from vehicle_controller.native import Bridge,Engine
    from vehicle_controller.host import Host
    from vehicle_controller import take
    bridge=Bridge(repo);control,_=bridge.initial(0);control['events']['enabled']=1
    value=take.create(bridge,0,control)
    control['events'].update(manual_type=2,manual_sequence=1);take.append(value,137,control)
    control['gain']=.3;take.append(value,211,control);value['frames']=960
    with Engine(bridge,0) as engine:
        engine.set(value['initial']);engine.process(137);engine.set(value['events'][0]['control'])
        engine.process(74);expected=deepcopy(engine.last_events)
    rows=[]
    for known in (False,True):
        played=deepcopy(value);played['source_events']=deepcopy(expected) if known else []
        host=Host(bridge,0,played['initial'],played);host.update(played['initial'],muted=True)
        host.start();host.thread.join(5)
        if host.thread.is_alive():host.stop();host.thread.join(2);raise AssertionError('Test host did not finish')
        state=host.snapshot();saved=host.take_snapshot()
        rows.append(dict(recorded_input_notices=known,state=state,expected=expected,actual=saved['source_events'],
                         frames=saved['frames'],passed=saved['source_events']==expected and saved['frames']==960 and not state.get('error')))
        take.save(a.output/('recorded' if known else 'control_only'),saved)
    report=dict(schema='vsl.vehicle-host-replay-verification/1',cases=rows,goal_complete=False,
                method='Bounded muted real WinMM host, no persistent service.')
    (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)
    assert all(row['passed'] for row in rows),'The host did not record actual replay event notices'


if __name__=='__main__':main()
