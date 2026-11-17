"""Bounded owned Tk/WinMM test: startup editing, recipes and full-cycle replay."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    import tkinter as tk
    from PIL import ImageGrab
    from vehicle_controller.ui import Window
    from vehicle_controller import startup,recipe,take
    from vehicle_scenarios.capture import replay
    repo=Path(__file__).resolve().parents[1]
    from startup_response_evidence_v1 import capture,verify
    binding=capture(repo,a.output)
    root=tk.Tk();window=Window(root,repo,a.output/'takes')
    def pump(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:root.update();time.sleep(.005)
    report=dict(schema='vsl.startup-response-ui-verification/1',goal_complete=False,timbre_accepted=False,
        method='Bounded owned Tk actions and own-HWND screenshots; muted WinMM; no persistent launch/restart.')
    try:
        pump(.15);assert not window.running();default=deepcopy(window.startup_response)
        window.startup_button.invoke();pump(.1);panel=window.startup_panel;assert panel
        assert len(panel.inputs)==9
        panel.vars['crank_seconds'].set('nan');panel.apply();assert window.startup_panel is panel
        assert window.startup_response==default
        panel.default_button.invoke();assert all(float(panel.vars[k].get())==v for k,v in default.items())
        panel.reference_button.invoke();assert float(panel.vars['flare_rpm'].get())==2000
        panel.vars['crank_seconds'].set('.5');panel.vars['catch_rise_seconds'].set('.35')
        panel.vars['catch_settle_seconds'].set('.8');panel.vars['combustion_seconds'].set('.1')
        panel.vars['stopping_seconds'].set('.8');panel.vars['stopping_tau'].set('.15')
        pump(.1);ImageGrab.grab(window=panel.root.winfo_id()).save(a.output/'startup-panel.png')
        # Ensure the last controls are inside the popup's client region.
        for button in (panel.default_button,panel.reference_button):
            assert button.winfo_rooty()+button.winfo_height()<panel.root.winfo_rooty()+panel.root.winfo_height()
        expected=startup.validate({k:float(v.get()) for k,v in panel.vars.items()})
        panel.apply();pump(.1);assert window.startup_panel is None and window.startup_response==expected
        preset_path=a.output/'custom.preset.json'
        with patch('vehicle_controller.ui.filedialog.asksaveasfilename',return_value=str(preset_path)):window.save()
        saved=json.loads(preset_path.read_text(encoding='utf-8'));recipe.validate(window.bridge,saved)
        assert saved['startup_response']==expected
        window.startup_response=default
        with patch('vehicle_controller.ui.filedialog.askopenfilename',return_value=str(preset_path)):window.restore()
        assert window.startup_response==expected
        window.event_panel.enabled.set(1);window.vars['gain'].set(.19);window.muted.set(1)
        window.demo_button.invoke();pump(.25)
        assert window.running() and window.replaying
        assert window.host.startup_response==window.host.replay['startup_response']==expected
        assert window.startup_button.instate(['disabled'])
        window.edit_startup();assert window.startup_panel is None
        host=window.host;deadline=time.monotonic()+48;peak=0.;noted=False;snapshots=[];last=-1
        while window.running() and time.monotonic()<deadline:
            pump(.02);state=host.snapshot()
            if state.get('error'):raise AssertionError(state)
            seconds=state.get('frame',0)/48000
            if seconds<2.5:peak=max(peak,state.get('rpm',0))
            if seconds//5>last:
                last=seconds//5;snapshots.append(state)
                print(json.dumps(dict(seconds=seconds,underflows=state.get('underflows'))),flush=True)
            if not noted and seconds>2:
                ImageGrab.grab(window=root.winfo_id()).save(a.output/'replay.png');noted=True
        pump(.1);assert not window.running() and noted
        state=host.snapshot();assert not state.get('error') and state['frame']==32*48000 and state['lifecycle']==0,state
        assert peak>1950,peak
        assert state['event_overflow']==state['event_log_lost']==0
        assert window.startup_button.instate(['!disabled'])
        window.save_take();paths=list((a.output/'takes').glob('*.vsltake.json'));assert len(paths)==1
        value=take.read(paths[0],window.bridge);assert value['startup_response']==expected
        assert value['source_events'] and value['source_events']==host.take_snapshot()['source_events']
        # The actual recorded host controls must reproduce notices and final C state.
        repeated=replay(window.bridge,value)
        assert repeated['source_events']==value['source_events']
        for key,number in repeated['final_state'].items():assert state[key]==number,(key,state[key],number)
        report.update(result='passed',native_defaults=default,startup_response=expected,
            no_autoplay=True,invalid_edit_preserves_configuration=True,preset_roundtrip=True,
            full_lifecycle_uses_custom_response=True,edit_locked_during_playback=True,
            saved_take_carries_response=True,actual_notice_replay_exact=True,
            final_state_replay_exact=True,observed_startup_peak=peak,final_state=state,snapshots=snapshots)
        verify(repo,binding)
        report['source_binding_sha256']=__import__('hashlib').sha256((a.output/'source_binding.json').read_bytes()).hexdigest()
        take.save(a.output/'report.json',report)
    finally:
        window.stop();deadline=time.monotonic()+5
        while window.running() and time.monotonic()<deadline:pump(.02)
        if window.startup_panel:window.startup_panel.close()
        root.destroy()
    print(json.dumps(dict(result=report['result'],peak=report['observed_startup_peak'])),flush=True)


if __name__=='__main__':
    try:main()
    except Exception:
        import traceback
        if '--output' in sys.argv:
            folder=Path(sys.argv[sys.argv.index('--output')+1]);folder.mkdir(parents=True,exist_ok=True)
            (folder/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
