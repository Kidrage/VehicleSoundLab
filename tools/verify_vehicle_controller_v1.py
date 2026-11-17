"""Verify actual C bridge, replay, silent WinMM and application-owned Tk controls."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--ui',action='store_true');args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    from vehicle_controller.native import Bridge,Engine
    from vehicle_controller import take
    from vehicle_controller.render import export
    bridge=Bridge(Path(__file__).resolve().parents[1]);control,features=bridge.initial(0)
    original_identity=bridge.voices_sha256;bridge.voices_sha256='0'*64
    try:Engine(bridge,0)
    except RuntimeError:pass
    else:raise AssertionError('Changed live parameter identity was accepted')
    finally:bridge.voices_sha256=original_identity
    control.update(ignition=1,start_id=1,mode=1);control['input']['sequence']=1
    value=take.create(bridge,0,control);original=bytearray();zero=deepcopy(control)
    with Engine(bridge,0) as engine:
        engine.set(control)
        for block in range(300):
            if block==100:control['throttle']=.8
            if block==220:control['throttle']=0
            control['input']['sequence']+=1;engine.set(control);take.append(value,engine.frame,engine.controls)
            original.extend(engine.process())
        value['frames']=engine.frame
    take_path=args.output/'script.vsltake.json';take.save(take_path,value);loaded=take.read(take_path,bridge)
    bad=deepcopy(value);bad['voices_sha256']='0'*64;take.save(args.output/'wrong-parameters.vsltake.json',bad)
    try:take.read(args.output/'wrong-parameters.vsltake.json',bridge)
    except ValueError:pass
    else:raise AssertionError('Changed parameter identity was accepted')
    rendered=export(bridge,loaded,args.output/'replayed',False)
    assert Path(rendered['paths'][0]).read_bytes()[44:]==original,'Recorded controls did not reproduce PCM'
    full=export(bridge,loaded,args.output/'stems',True)
    # The exporter now includes an event-identity JSON sidecar as well as WAVs.
    assert len([p for p in full['paths'] if Path(p).suffix=='.wav'])==len(bridge.stems)+1
    assert len(full['paths'])==len(bridge.stems)+2
    sidecar=json.loads(Path(full['paths'][-1]).read_text(encoding='utf-8'))
    assert sidecar['frames']==value['frames'] and sidecar['source_effective_sha256']==value['source_effective_sha256']
    from vehicle_controller.device import Output
    with Output() as device:
        deadline=time.monotonic()+3
        while device.submitted<18:
            assert time.monotonic()<deadline,'WinMM did not finish buffers'
            if device.ready():device.write(bytes(480*8))
            else:time.sleep(.001)
        device.drain();assert device.queued()==0
    report=dict(schema='vsl.vehicle-controller-verification/1',bridge_sha256=bridge.sha256,
        voices_sha256=bridge.voices_sha256,parameter_identity_mismatch_rejected=True,
        changed_live_parameter_identity_rejected=True,
        replay_pcm_exact=True,script_frames=value['frames'],native_stem_channels=bridge.channels(),silent_device_blocks=18,
        script_sha256=hashlib.sha256(original).hexdigest(),ui=False)
    if args.ui:
        import tkinter as tk
        from vehicle_controller.ui import Window,MODES
        root=tk.Tk();window=Window(root,Path(__file__).resolve().parents[1],args.output/'takes')
        def advance(seconds):
            end=time.monotonic()+seconds
            while time.monotonic()<end:root.update();time.sleep(.005)
        try:
            root.update();assert window.widgets['startup_gain'][0].instate(['disabled'])
            window.muted.set(1);window.mode.set(MODES[3]);window.automatic.set(0);window.gear.set(1)
            window.vars['external_speed'].set(72);window.vars['external_acceleration'].set(2);window.vars['tire_slip'].set(.2)
            window.start();advance(2.2);state=window.host.snapshot()
            assert not state.get('error'),state
            assert state['input_source']==1 and not state['input_stale'] and abs(state['speed_mps']-20)<1e-9,state
            window.pause_signals.set(1);advance(.8);state=window.host.snapshot()
            assert state['input_stale'] and state['acceleration_mps2']==0 and state['speed_mps']==20,state
            window.pause_signals.set(0);advance(.25);assert not window.host.snapshot()['input_stale']
            window.keys.add('w');advance(.15);assert window.vars['throttle'].get()>.1
            window.key_up(SimpleNamespace(keysym='w'));assert window.vars['throttle'].get()==0
            window.keys.add('w');root.withdraw();advance(.1);window.release_if_unfocused();assert not window.keys
            root.deiconify();advance(.1);window.ignition_off();advance(.15)
            assert window.host.snapshot()['lifecycle']==5
            window.start();advance(2.4);assert window.host.snapshot()['lifecycle']==4,'Restart during stopping was swallowed'
            window.save_take();assert list((args.output/'takes').glob('*.vsltake.json'))
            sys.path.insert(0,'E:/VehicleSoundLab/tools/python_deps')
            from PIL import ImageGrab
            for index,name in enumerate(('drive','tone','signals')):
                window.tabs.select(index);advance(.1)
                # Capture our own HWND, not desktop pixels from an occluding app.
                picture=ImageGrab.grab(window=root.winfo_id())
                assert picture.width>=900 and picture.height>=650,picture.size
                picture.save(args.output/(name+'.png'))
            hashes=[hashlib.sha256((args.output/(name+'.png')).read_bytes()).hexdigest() for name in ('drive','tone','signals')]
            assert len(set(hashes))==3,'Tab screenshots were identical; target capture is not verified'
            window.tabs.select(0);report.update(ui=True,ui_method='application-owned Tk actions and own-HWND captures; no external OS automation',
                external_speed_adopted=True,timeout_and_resume=True,key_release=True,focus_loss_release=True,
                disabled_missing_model_controls=True,ui_saved_take=True,ui_final_state=window.host.snapshot())
            report['restart_during_stopping']=True
        finally:
            window.stop()
            deadline=time.monotonic()+3
            while window.running() and time.monotonic()<deadline:root.update();time.sleep(.01)
            root.destroy()
    (args.output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
    try:main()
    except Exception:
        import traceback
        if '--output' in sys.argv:
            folder=Path(sys.argv[sys.argv.index('--output')+1])
            if folder.is_dir():(folder/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
