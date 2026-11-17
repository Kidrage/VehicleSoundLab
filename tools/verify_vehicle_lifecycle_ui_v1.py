"""Bounded, muted, application-owned full-cycle test of the independent UI."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,'E:/VehicleSoundLab/tools/python_deps')
    import tkinter as tk
    from PIL import ImageGrab
    from vehicle_controller.ui import Window
    from vehicle_controller import take
    from vehicle_scenarios.scenario import sport_lifecycle
    repo=Path(__file__).resolve().parents[1]
    for relative in ('tools/verify_vehicle_lifecycle_ui_v1.py','tools/vehicle_scenarios/scenario.py',
                     'tools/vehicle_controller/ui.py','tools/vehicle_controller/host.py','tools/vehicle_controller/take.py'):
        target=a.output/'exact_sources'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/relative,target)
    root=tk.Tk();window=Window(root,repo,a.output/'takes')
    def pump(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:root.update();time.sleep(.005)
    report=dict(schema='vsl.vehicle-lifecycle-ui-verification/1',goal_complete=False,timbre_accepted=False,
                method='Owned Tk actions and own-HWND screenshots; muted WinMM device; bounded lifetime.')
    try:
        pump(.15);assert not window.running()
        window.vars['detail'].set(.83);window.vars['gain'].set(.19)
        window.event_panel.enabled.set(1);window.vars['event_gain'].set(.4)
        control=window.controls();original=deepcopy(control)
        planned,_=sport_lifecycle(window.bridge,0,control=control)
        assert control==original and planned['initial']['detail']==.83 and planned['initial']['gain']==.19
        assert planned['initial']['events']['gain']==.4 and planned['initial']['events']['enabled']==1
        window.event_panel.enabled.set(0)
        off,_=sport_lifecycle(window.bridge,0,control=window.controls())
        assert off['initial']['events']['enabled']==0
        window.event_panel.enabled.set(1);window.muted.set(1)
        ImageGrab.grab(window=root.winfo_id()).save(a.output/'before.png')
        window.demo_button.invoke();pump(.4)
        assert window.running() and window.replaying
        assert window.vars['detail'].get()==.83 and window.vars['gain'].get()==.19
        initial=deepcopy(window.host.replay['initial']);host=window.host
        window.demo_button.invoke();assert window.host is host and window.host.replay['initial']==initial
        deadline=time.monotonic()+48;captured=False;snapshots=[];last_logged=-1
        solo_on=False;solo_off=False
        while window.running() and time.monotonic()<deadline:
            pump(.04);state=window.host.snapshot()
            if state.get('error'):raise AssertionError(state)
            seconds=state.get('frame',0)/48000
            if seconds//4>last_logged:
                last_logged=seconds//4;snapshots.append(state)
                print(json.dumps(dict(seconds=seconds,underflows=state.get('underflows'),state=state.get('operating'))),flush=True)
            if not captured and seconds>7:
                ImageGrab.grab(window=root.winfo_id()).save(a.output/'driving.png');captured=True
            if seconds>10 and not solo_on:window.solo.set('DNA');solo_on=True
            if seconds>12 and not solo_off:window.solo.set('完整干声');solo_off=True
            if 5<seconds<14:
                assert abs(window.vars['throttle'].get()-.92)<1e-12
                assert window.vars['brake'].get()==0 and window.widgets['throttle'][0].instate(['disabled'])
                assert window.start_button.instate(['disabled'])
        pump(.1);assert not window.running(),'Bounded demo did not complete'
        final=window.host.snapshot();assert final.get('frame')==32*48000 and not final.get('error'),final
        assert final['lifecycle']==0 and final['event_started']==2 and final['event_peak']<=4
        assert final['event_overflow']==final['event_log_lost']==0
        assert not window.replaying and captured
        assert window.widgets['throttle'][0].instate(['!disabled']) and window.start_button.instate(['!disabled'])
        button=window.demo_button
        assert button.winfo_ismapped() and button.winfo_rootx()+button.winfo_width()<root.winfo_rootx()+root.winfo_width()
        window.save_take();paths=list((a.output/'takes').glob('*.vsltake.json'));assert len(paths)==1
        saved=take.read(paths[0],window.bridge);assert saved['frames']==32*48000 and len(saved['source_events'])==4
        assert saved['initial']['detail']==.83 and saved['initial']['gain']==.19
        ImageGrab.grab(window=root.winfo_id()).save(a.output/'finished.png')
        report.update(result='passed',no_autoplay=True,demo_32_seconds=True,current_tone_preserved=True,
            event_enable_preserved=True,input_not_mutated=True,one_active_host=True,solo_switching=solo_on and solo_off,
            replay_displays_adopted_pedals=True,replay_controls_locked_then_restored=True,
            event_notices_in_saved_take=4,snapshots=snapshots,final_state=final,
            screenshot_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in a.output.glob('*.png')})
    finally:
        window.stop();deadline=time.monotonic()+4
        while window.running() and time.monotonic()<deadline:pump(.02)
        root.destroy()
    (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(result=report['result'],final=report['final_state']),ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except Exception:
        import traceback
        if '--output' in sys.argv:
            folder=Path(sys.argv[sys.argv.index('--output')+1]);folder.mkdir(parents=True,exist_ok=True)
            (folder/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
