"""Original V4 oracle: normal sounds exact, startup interruption releases only events."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    sys.path.insert(0,'E:/VehicleSoundLab/tools/python_deps')
    import numpy as np
    from vehicle_controller.native import Bridge,Engine
    from vehicle_controller import take
    from vehicle_scenarios.capture import replay
    from startup_response_evidence_v1 import capture,verify,sha
    repo=Path(__file__).resolve().parents[1];a.output.mkdir(parents=True,exist_ok=False)
    new=Bridge(repo);old=Bridge(repo,repo/'build-vehicle-source-v4/bin/Release/vsl_source_bridge.dll')
    assert old.sha256=='d0f864e824df83e136613fd8b50a64c3234dbda23a84647afe511f760243bcb3'
    binding=capture(repo,a.output,new.path);shutil.copy2(__file__,a.output/'executed_verification.py')
    width=new.channels();event_offset=sum(r['channels'] for r in new.stems[:12]);exact=[]
    def render(bridge,selection,control,changes,frames):
        mix=[];native=[];notices=[];states=[];index=0
        with Engine(bridge,selection) as engine:
            engine.set(control)
            while engine.frame<frames:
                if index<len(changes) and engine.frame==changes[index][0]:
                    control=deepcopy(control);control.update(changes[index][1]);engine.set(control);index+=1
                size=min(480,frames-engine.frame,changes[index][0]-engine.frame if index<len(changes) else frames)
                mix.append(engine.process(size))
                native.append(np.ctypeslib.as_array(engine.stems)[:size*width].reshape(size,width).copy())
                states.append(engine.state());notices.extend(engine.last_events)
        return dict(pcm=b''.join(mix),native=np.concatenate(native),notices=notices,states=states)
    for row in new.catalog:
        for enabled in (0,1):
            control=new.initial(row['id'])[0];control.update(mode=1,ignition=0,start_id=0,gear=0,automatic=0,throttle=0.,brake=.7)
            control['events']['enabled']=enabled
            changes=[(10013,dict(ignition=1,start_id=1)),(80017,dict(throttle=.35)),(120019,dict(ignition=0,throttle=0.))]
            left=render(old,row['id'],deepcopy(control),changes,153600);right=render(new,row['id'],control,changes,153600)
            assert left['pcm']==right['pcm'] and np.array_equal(left['native'],right['native']),(row,enabled,'audio')
            assert left['states']==right['states'] and left['notices']==right['notices'],(row,enabled,'state')
            exact.append(dict(catalog=row['key'],events=enabled,frames=153600))
        print(json.dumps(dict(original_v4_exact=row['key'])),flush=True)
    cases=[]
    for off_frame,decay in ((7200,1.),(21600,1.),(21733,4.)):
        control=new.initial(1)[0];control.update(mode=1,ignition=1,start_id=1,gear=0,automatic=0,throttle=0.,brake=.7)
        control['events'].update(enabled=1,decay=decay)
        left=render(old,1,deepcopy(control),[(off_frame,dict(ignition=0))],192000)
        right=render(new,1,control,[(off_frame,dict(ignition=0))],192000)
        assert np.array_equal(left['native'][:,:event_offset],right['native'][:,:event_offset])
        assert np.array_equal(left['native'][:off_frame],right['native'][:off_frame])
        catch_ends=[n for n in right['notices'] if n['type']==2 and n['action']==2]
        if off_frame>13440:
            expected=((off_frame+239)//240)*240+960
            assert len(catch_ends)==1 and catch_ends[0]['frame']==expected and catch_ends[0]['reason']==1,catch_ends
        assert not abs(right['native'][60000:,event_offset:]).max()
        cases.append(dict(ignition_off_frame=off_frame,decay=decay,continuous_stems_exact=True,pre_stop_all_stems_exact=True,catch_ends=catch_ends))
    # OFF manual audition is intentional and must still run its full natural tail.
    control=new.initial(1)[0];control.update(mode=1,ignition=0,start_id=0)
    control['events'].update(enabled=1,manual_type=2,manual_sequence=1,decay=4.)
    left=render(old,1,deepcopy(control),[],192000);right=render(new,1,control,[],192000)
    assert left['pcm']==right['pcm'] and left['notices']==right['notices']
    assert any(n['type']==2 and n['action']==2 and n['frame']==153600 and n['reason']==0 for n in right['notices'])
    # Native start edges are issued after OFF. The separate UI owns its pending
    # restart button intent while STOPPING; it is tested through the real window.
    control=new.initial(1)[0];control.update(mode=1,ignition=1,start_id=1,gear=0,automatic=0,throttle=0.,brake=.7)
    control['events'].update(enabled=1,decay=4.)
    value=take.create(new,1,control);value['frames']=240000
    for frame,changes in ((21600,dict(ignition=0)),(56000,dict(ignition=1,start_id=2)),(200000,dict(ignition=0))):
        control.update(changes);take.append(value,frame,control)
    reference=replay(new,value,block_pattern=(480,));variable=replay(new,value)
    assert reference['pcm_sha256']==variable['pcm_sha256'] and reference['source_events']==variable['source_events']
    starts=[n for n in reference['source_events'] if n['action']==1]
    assert [n['type'] for n in starts].count(1)==2 and [n['type'] for n in starts].count(2)==2
    assert reference['final_state']==variable['final_state'] and reference['final_state']['lifecycle']==0
    value['source_events']=reference['source_events'];take.save(a.output/'restart.vsltake.json',value)
    verify(repo,binding)
    report=dict(schema='vsl.startup-stop-regression/1',result='passed',goal_complete=False,timbre_accepted=False,
        old_bridge_sha256=old.sha256,bridge_sha256=new.sha256,voice_bank_sha256=new.voices_sha256,
        abi=new.abi(),normal_original_v4_exact=exact,abort_cases=cases,manual_OFF_full_tail_exact=True,
        restart=reference,source_binding_sha256=sha(a.output/'source_binding.json'))
    (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(result='passed',normal_cases=len(exact),abort_cases=len(cases),restart_starts=len(starts))))


if __name__=='__main__':
    try:main()
    except Exception:
        import traceback
        if '--output' in sys.argv:
            folder=Path(sys.argv[sys.argv.index('--output')+1]);folder.mkdir(parents=True,exist_ok=True)
            (folder/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
