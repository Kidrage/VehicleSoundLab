"""Authored event -> per-engine C override -> automatic/manual playback -> replay."""
import argparse
from copy import deepcopy
import ctypes as ct
import json
from pathlib import Path
import shutil
import sys
import time
import traceback


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--package',type=Path,required=True);parser.add_argument('--ui',action='store_true')
    a=parser.parse_args();a.output.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.output/'executed_verification.py')
    sys.path.insert(0,'E:/VehicleSoundLab/tools/python_deps')
    import numpy as np
    import soundfile as sf
    from event_authoring.contract import pack_profile
    from vehicle_controller.native import Bridge,Engine
    from vehicle_controller import take,recipe,event_profiles
    from vehicle_controller.render import export
    repo=Path(__file__).resolve().parents[1];bridge=Bridge(repo)
    real=event_profiles.document(json.loads(a.package.read_text(encoding='utf-8')))
    # This explicitly synthetic fixture tests a previously unavailable type. It is not a real afterfire timbre.
    profile=dict(gated=0,duration_seconds=.22,attack_seconds=.001,release_seconds=.015,sweep_seconds=.06,level=.1,
        modes=[dict(hz=190,end_hz=85,amplitude=.3,phase=.2,decay_seconds=.045)],
        bands=[dict(hz=1700,q=.8,amplitude=.15,attack_seconds=.001,decay_seconds=.025)])
    synthetic=dict(schema='vsl.event-profile/1',kind='afterfire',name='Known event fixture, not a vehicle afterfire',
        parameters=profile,status='synthetic verification only',physical_identity_confirmed=False)
    overrides={'catch':real,'afterfire':synthetic};overrides=event_profiles.validate_overrides(overrides)
    custom=a.output/'synthetic_event_parameters.json';custom.write_text(json.dumps(synthetic),encoding='utf-8')
    real_path=a.output/'A_catch_parameters.json';real_path.write_text(json.dumps(real,ensure_ascii=False,indent=2),encoding='utf-8')
    report=dict(schema='vsl.authored-event-flow-verification/1',goal_complete=False,hearing_accepted=False,
        abi=bridge.abi(),bridge_sha256=bridge.sha256,voices_sha256=bridge.voices_sha256,
        event_effective_sha256=event_profiles.identity(bridge,overrides))
    control,_=bridge.initial(0);control['events'].update(enabled=1,manual_type=3,manual_sequence=1)
    with Engine(bridge,0) as base:
        try:base.set(control)
        except ValueError:pass
        else:raise AssertionError('Missing event accepted by control validation')
        base.process(480);baseline=base.state();assert baseline['event_started']==0
    with Engine(bridge,0,overrides) as engine:
        engine.set(control);engine.process(480);assert engine.state()['event_started']==1
        native=pack_profile(profile)
        assert bridge.event_profile(engine.handle,3,ct.byref(native))==0
    # The copied C parameters and engine-local setup are independent of host JSON mutation.
    original=deepcopy(overrides)
    with Engine(bridge,0,overrides) as one,Engine(bridge,0,original) as two:
        overrides['afterfire']['parameters']['modes'][0]['hz']=900
        one.set(control);two.set(control)
        assert one.process(480)==two.process(480)
    overrides=original
    with Engine(bridge,0,overrides) as engine:
        engine.set(control)
        assert bridge.event_profile(engine.handle,3,ct.byref(pack_profile(profile)))==0  # queued frame-zero event
    # Startup through idle plus two manual events, deliberately away from the 200 Hz grid.
    control,_=bridge.initial(0);control.update(ignition=1,start_id=1)
    control['events']['enabled']=1
    value=take.create(bridge,0,control,overrides);pcm=[];frames=192000
    changes={17333:dict(manual_type=3,manual_sequence=1),24361:dict(manual_type=3,manual_sequence=2)}
    with Engine(bridge,0,overrides) as engine:
        engine.set(control)
        while engine.frame<frames:
            if engine.frame in changes:
                control['events'].update(changes[engine.frame]);engine.set(control);take.append(value,engine.frame,control)
            end=min(engine.frame+480,frames,*[frame for frame in changes if frame>engine.frame])
            pcm.append(engine.process(end-engine.frame));value['source_events'].extend(engine.last_events)
        state=engine.state()
    value['frames']=frames;take.save(a.output/'authored.vsltake.json',value)
    loaded=take.read(a.output/'authored.vsltake.json',bridge);replay=export(bridge,loaded,a.output/'replay')
    actual,sr=sf.read(a.output/'replay_mix.wav',dtype='float32',always_2d=True)
    direct=np.frombuffer(b''.join(pcm),dtype='<f4').reshape(-1,2)
    assert sr==48000 and np.array_equal(actual,direct) and replay['source_events']==value['source_events']
    assert all(any(e['action']==1 and e['type']==3 and e['frame']==frame for e in value['source_events']) for frame in changes)
    assert any(e['action']==1 and e['type']==1 for e in value['source_events']) and any(e['action']==1 and e['type']==2 for e in value['source_events'])
    assert state['event_peak']<=4 and state['event_overflow']==state['event_log_lost']==0
    tampered=deepcopy(value);tampered['event_overrides']['afterfire']['parameters']['level']*=.5
    take.save(a.output/'tampered.vsltake.json',tampered)
    try:take.read(a.output/'tampered.vsltake.json',bridge)
    except ValueError:pass
    else:raise AssertionError('Tampered recipe accepted')
    authored_recipe=recipe.create(bridge,0,control,'fixture',overrides)
    assert recipe.validate(bridge,authored_recipe)==overrides
    authored_recipe['event_overrides']['afterfire']['parameters']['level']*=.7
    try:recipe.validate(bridge,authored_recipe)
    except ValueError:pass
    else:raise AssertionError('Tampered preset accepted')
    # Five requests within one active event: bounded capacity remains four, with explicit rejection.
    control,_=bridge.initial(0);control['events'].update(enabled=1,manual_type=3,manual_sequence=1)
    with Engine(bridge,0,overrides) as engine:
        notices=[];engine.set(control)
        for sequence in range(2,7):
            engine.process(17);notices.extend(engine.last_events)
            control['events']['manual_sequence']=sequence;engine.set(control)
        engine.process(17);notices.extend(engine.last_events);pool=engine.state()
        assert pool['event_peak']==4 and pool['event_rejected']>=1 and any(e['reason']==3 for e in notices)
    report.update(per_engine_copies_are_independent=True,frame_zero_queue_and_running_replacement_refused=True,
        missing_default_type_explicit=True,new_type_uses_same_core=True,replay_pcm_exact=True,replay_notices_exact=True,
        manual_frames=list(changes),automatic_start_and_catch=True,peak_voices=pool['event_peak'],
        tampered_take_and_preset_refused=True,native_stems=bridge.channels(),final_state=state)
    if a.ui:
        import tkinter as tk
        from tkinter import filedialog
        from PIL import ImageGrab
        from vehicle_controller.ui import Window
        root=tk.Tk();window=Window(root,repo,a.output/'ui_takes')
        def pump(seconds):
            end=time.monotonic()+seconds
            while time.monotonic()<end:root.update();time.sleep(.01)
        try:
            window.tabs.select(window.events_page);pump(.1)
            assert window.event_panel.buttons[3].instate(['disabled'])
            window.event_panel.import_profile(custom);window.event_panel.import_profile(real_path);pump(.1)
            assert window.event_panel.buttons[3].instate(['!disabled']) and len(window.event_overrides)==2
            window.muted.set(1);window.event_panel.audition(3);pump(.6)
            state=window.host.snapshot();assert state.get('event_started')==1 and not state.get('error'),state
            old=deepcopy(window.event_overrides);window.event_panel.reset_profiles();assert window.event_overrides==old
            window.event_panel.import_profile(custom);assert window.event_overrides==old
            window.stop();deadline=time.monotonic()+4
            while window.running() and time.monotonic()<deadline:pump(.02)
            assert not window.running()
            path=a.output/'custom_vehicle_recipe.json';previous=filedialog.asksaveasfilename
            try:filedialog.asksaveasfilename=lambda **kw:str(path);window.save()
            finally:filedialog.asksaveasfilename=previous
            window.event_panel.reset_profiles();assert window.event_panel.buttons[3].instate(['disabled'])
            previous=filedialog.askopenfilename
            try:filedialog.askopenfilename=lambda **kw:str(path);window.restore()
            finally:filedialog.askopenfilename=previous
            assert window.event_overrides==old and window.event_panel.buttons[3].instate(['!disabled'])
            window.save_take();saved=list((a.output/'ui_takes').glob('*.vsltake.json'));assert saved
            assert take.read(saved[0],bridge)['event_overrides']==old
            pump(.1);ImageGrab.grab(window=root.winfo_id()).save(a.output/'controller_events.png')
            assert all(button.winfo_rooty()+button.winfo_height()<root.winfo_rooty()+root.winfo_height() for button in window.event_panel.buttons)
            report['ui']=dict(own_Tk_and_HWND=True,imported_types_enabled=True,live_import_and_reset_refused=True,
                recipe_restores_profiles=True,recorded_take_embeds_profiles=True,muted=True,state=state)
        finally:
            window.stop();deadline=time.monotonic()+4
            while window.running() and time.monotonic()<deadline:pump(.02)
            root.destroy()
    report['result']='passed';(a.output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except Exception:
        if '--output' in sys.argv:
            out=Path(sys.argv[sys.argv.index('--output')+1]);out.mkdir(exist_ok=True,parents=True)
            (out/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
