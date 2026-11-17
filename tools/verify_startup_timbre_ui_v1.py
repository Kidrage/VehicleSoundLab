"""Owned muted V6 window: import real colored profiles, recipe, drive and restart."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import time
from unittest.mock import patch

from startup_response_evidence_v1 import capture,verify,sha
from vehicle_controller import recipe,take
from vehicle_scenarios.capture import replay


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--delivery',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    import tkinter as tk
    from PIL import ImageGrab
    from vehicle_controller.ui import Window
    repo=Path(__file__).resolve().parents[1];projects=json.loads((a.delivery/'projects/report.json').read_text(encoding='utf-8'))
    root=tk.Tk();window=Window(root,repo,a.output/'takes');binding=capture(repo,a.output,window.bridge.path)
    shutil.copy2(__file__,a.output/'executed_verification.py')
    def pump():root.update();time.sleep(.005)
    def until(predicate,seconds=8):
        deadline=time.monotonic()+seconds;state={}
        while time.monotonic()<deadline:
            pump();state=window.host.snapshot() if window.host else {}
            if state.get('error'):raise AssertionError(state)
            if predicate(state):return state
        raise AssertionError(('Window deadline',state))
    try:
        until(lambda _:True);assert root.title().endswith('V6') and not window.running()
        window.load(0)
        for row in projects['projects']:window.event_panel.import_profile(row['parameters'])
        assert set(window.event_overrides)=={'crank','catch'} and window.event_panel.available_mask()==6
        for key,value in window.event_overrides.items():assert value['parameters']['noise_lowpass_hz']==10000
        window.event_panel.describe(2);assert '10 kHz' in window.event_panel.model_info.get()
        window.tabs.select(window.events_page);root.update_idletasks()
        ImageGrab.grab(window=root.winfo_id()).save(a.output/'imported-events.png')
        window.event_panel.enabled.set(1);window.muted.set(1)
        preset=a.output/'colored-startup.recipe.json'
        with patch('vehicle_controller.ui.filedialog.asksaveasfilename',return_value=str(preset)):window.save()
        saved=json.loads(preset.read_text(encoding='utf-8'));recipe.validate(window.bridge,saved)
        before=deepcopy(window.event_overrides);window.event_overrides={}
        with patch('vehicle_controller.ui.filedialog.askopenfilename',return_value=str(preset)):window.restore()
        assert window.event_overrides==before
        window.tabs.select(window.drive);window.demo_button.invoke()
        until(lambda s:s.get('active') and s.get('frame',0)>4800)
        host=window.host;assert host.event_overrides==before
        # Import during playback is refused without changing the running model.
        window.event_panel.import_profile(projects['projects'][0]['parameters']);assert window.event_overrides==before
        until(lambda s:s.get('frame',0)>=4*48000,seconds=9)
        root.update_idletasks();ImageGrab.grab(window=root.winfo_id()).save(a.output/'driving.png')
        until(lambda _:not window.running(),seconds=40);final=host.snapshot()
        assert final['frame']==32*48000 and final['lifecycle']==0 and final['underflows']==0,final
        window.save_take();paths=list((a.output/'takes').glob('*.vsltake.json'));assert len(paths)==1
        recorded=take.read(paths[0],window.bridge);assert recorded['event_overrides']==before
        replayed=replay(window.bridge,recorded);assert replayed['source_events']==recorded['source_events']
        for key,value in replayed['final_state'].items():assert final[key]==value,(key,final[key],value)
        # The colored catch profile also obeys cancellation and the UI restart queue.
        window.load(1);window.event_panel.enabled.set(1);window.vars['event_decay'].set(4.)
        window.start();until(lambda s:s.get('lifecycle')==3)
        window.ignition_off();until(lambda s:s.get('lifecycle')==5)
        window.start();assert window.pending_start
        until(lambda s:s.get('lifecycle')==3 and s.get('event_started',0)>=4)
        assert not window.pending_start;window.ignition_off()
        until(lambda s:s.get('lifecycle')==0 and s.get('event_active')==0)
        interrupted=window.host;window.stop();until(lambda _:not window.running())
        value=interrupted.take_snapshot();played=replay(window.bridge,value)
        assert played['source_events']==value['source_events']
        ends=[n for n in value['source_events'] if n['type']==2 and n['action']==2]
        assert len(ends)==2 and all(n['reason']==1 for n in ends)
        state=interrupted.snapshot();assert state['underflows']==state['event_overflow']==state['event_log_lost']==0,state
        take.save(a.output/'restart.vsltake.json',value);verify(repo,binding)
        report=dict(schema='vsl.startup-timbre-ui/1',result='passed',no_autoplay=True,
            two_colored_profiles_imported=True,recipe_exact=True,live_import_refused=True,
            full_32s_cycle=True,recorded_overrides_notices_and_state_replay_exact=True,final_state=final,
            colored_catch_cancel_restart=True,catch_ends=ends,restart_final_state=state,
            own_window_closed=True,source_binding_sha256=sha(a.output/'source_binding.json'),
            goal_complete=False,timbre_accepted=False)
        take.save(a.output/'report.json',report);print(json.dumps(dict(result='passed',underflows=final['underflows'],restart_underflows=state['underflows'])))
    finally:
        window.stop();deadline=time.monotonic()+5
        while window.running() and time.monotonic()<deadline:pump()
        root.destroy()


if __name__=='__main__':
    try:main()
    except Exception:
        import sys,traceback
        if '--output' in sys.argv:
            folder=Path(sys.argv[sys.argv.index('--output')+1]);folder.mkdir(parents=True,exist_ok=True)
            (folder/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
