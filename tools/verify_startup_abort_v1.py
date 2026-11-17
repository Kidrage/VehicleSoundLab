"""Observe startup event tails after ignition-off, using actual source C."""
import argparse
import json
from pathlib import Path
import shutil
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--library',type=Path);p.add_argument('--expect',choices=('tail','released'),required=True);a=p.parse_args()
    sys.path.insert(0,'E:/VehicleSoundLab/tools/python_deps')
    import numpy as np
    import soundfile as sf
    from vehicle_controller.native import Bridge,Engine
    from vehicle_controller import take
    from startup_response_evidence_v1 import capture,verify,sha
    repo=Path(__file__).resolve().parents[1];a.output.mkdir(parents=True,exist_ok=False)
    bridge=Bridge(repo,a.library);binding=capture(repo,a.output,bridge.path)
    shutil.copy2(__file__,a.output/'executed_verification.py')
    control=bridge.initial(1)[0];control.update(mode=1,ignition=1,start_id=1,gear=0,automatic=0,throttle=0.,brake=.7,gain=.25)
    control['events'].update(enabled=1,decay=4.)
    control['events']['levels']=[0.,1.,1.,0.,0.,0.,0.]
    value=take.create(bridge,1,control);value['frames']=4*48000
    control['ignition']=0;take.append(value,21600,control)
    frames=[];audio=[];stems=[];notices=[];index=0
    width=bridge.channels();event_offset=sum(s['channels'] for s in bridge.stems[:12])
    with Engine(bridge,1) as engine:
        engine.set(value['initial'])
        while engine.frame<value['frames']:
            pcm,index=take.replay_block(engine,value,index,240)
            audio.append(np.frombuffer(pcm,dtype='<f4').reshape(-1,2).copy())
            x=np.ctypeslib.as_array(engine.stems)[:240*width].reshape(240,width)
            stems.append(x[:,event_offset:].copy());frames.append(engine.state());notices.extend(engine.last_events)
    all_events=np.concatenate(stems);off=np.array([r['lifecycle']==0 for r in frames]).repeat(240)
    peak=float(abs(all_events[off]).max());tail=peak>1e-7
    assert tail==(a.expect=='tail'),(a.expect,peak)
    starts={n['id']:n for n in notices if n['action']==1}
    ends=[dict(id=n['id'],type=n['type'],start_frame=starts[n['id']]['frame'],end_frame=n['frame'],reason=n['reason'])
          for n in notices if n['action']==2]
    value['source_events']=notices;take.save(a.output/'abort.vsltake.json',value)
    sf.write(a.output/'mix.wav',np.concatenate(audio),48000,subtype='FLOAT')
    sf.write(a.output/'events.wav',all_events.sum(axis=1)*2**-.5,48000,subtype='FLOAT')
    verify(repo,binding)
    report=dict(schema='vsl.startup-abort-verification/1',result='passed',expected_observation=a.expect,
        goal_complete=False,timbre_accepted=False,bridge_path=str(bridge.path),bridge_sha256=bridge.sha256,
        has_event_tail_after_OFF=tail,OFF_event_peak=peak,ignition_off_frame=21600,
        first_OFF_frame=next(i*240 for i,r in enumerate(frames) if r['lifecycle']==0),
        event_lifetimes=ends,final_state=frames[-1],source_binding_sha256=sha(a.output/'source_binding.json'))
    (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except Exception:
        import traceback
        if '--output' in sys.argv:
            folder=Path(sys.argv[sys.argv.index('--output')+1]);folder.mkdir(parents=True,exist_ok=True)
            (folder/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
