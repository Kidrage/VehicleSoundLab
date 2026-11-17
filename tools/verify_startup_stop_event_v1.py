"""Known fixture only: releasing startup tails must preserve an independent STOP voice."""
import argparse
import json
from pathlib import Path
import shutil


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    from vehicle_controller.native import Bridge,Engine
    from startup_response_evidence_v1 import capture,verify,sha
    repo=Path(__file__).resolve().parents[1];a.output.mkdir(parents=True,exist_ok=False)
    bridge=Bridge(repo);binding=capture(repo,a.output,bridge.path)
    shutil.copy2(__file__,a.output/'executed_verification.py')
    profile=dict(schema='vsl.event-profile/1',kind='stop',name='KNOWN TEST FIXTURE ONLY',physical_identity_confirmed=False,
        parameters=dict(gated=0,duration_seconds=.8,attack_seconds=.003,release_seconds=.02,
            sweep_seconds=0.,level=1.,modes=[dict(hz=150.,end_hz=150.,amplitude=.1,phase=0.,decay_seconds=1.)],bands=[]))
    (a.output/'known-stop-fixture.json').write_text(json.dumps(profile,indent=2),encoding='utf-8')
    control=bridge.initial(1)[0];control.update(mode=1,ignition=1,start_id=1,gear=0,automatic=0,throttle=0.,brake=.7)
    control['events']['enabled']=1;notices=[]
    with Engine(bridge,1,{'stop':profile}) as engine:
        engine.set(control)
        while engine.frame<96000:
            if engine.frame==21600:control['ignition']=0;engine.set(control)
            engine.process(240);notices.extend(engine.last_events)
        final=engine.state()
    stop_start=next(n for n in notices if n['type']==6 and n['action']==1)
    stop_end=next(n for n in notices if n['type']==6 and n['action']==2)
    catch_end=next(n for n in notices if n['type']==2 and n['action']==2)
    assert stop_start['frame']==21600 and stop_end['frame']==60000 and stop_end['reason']==0
    assert catch_end['frame']==22560 and catch_end['reason']==1
    assert final['lifecycle']==0 and final['event_active']==final['event_rejected']==final['event_log_lost']==final['event_overflow']==0
    verify(repo,binding)
    result=dict(result='passed',goal_complete=False,timbre_accepted=False,known_fixture_only=True,
        global_bank_unchanged=True,catch_released=catch_end,STOP_natural_tail_preserved=stop_end,
        notices=notices,source_binding_sha256=sha(a.output/'source_binding.json'))
    (a.output/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))


if __name__=='__main__':main()
