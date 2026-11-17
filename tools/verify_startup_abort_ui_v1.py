"""Bounded owned muted window: cancel CATCH and queue a UI restart during STOPPING."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    import tkinter as tk
    from PIL import ImageGrab
    from vehicle_controller.ui import Window
    from vehicle_controller import take
    from vehicle_scenarios.capture import replay
    from startup_response_evidence_v1 import capture,verify,sha
    repo=Path(__file__).resolve().parents[1];a.output.mkdir(parents=True,exist_ok=False)
    root=tk.Tk();window=Window(root,repo,a.output/'takes');binding=capture(repo,a.output,window.bridge.path)
    shutil.copy2(__file__,a.output/'executed_verification.py')
    def pump():root.update();time.sleep(.005)
    def until(predicate,seconds=6):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            pump();state=window.host.snapshot() if window.host else {}
            if state.get('error'):raise AssertionError(state)
            if predicate(state):return state
        raise AssertionError(('Window state deadline',state))
    try:
        until(lambda _:True);assert not window.running() and root.title().endswith('V5')
        window.load(1);window.event_panel.enabled.set(1);window.vars['event_decay'].set(4.);window.muted.set(1)
        window.start();until(lambda s:s.get('lifecycle')==3)
        window.ignition_off();until(lambda s:s.get('lifecycle')==5 and '停机' in window.state.get())
        window.start();assert window.pending_start
        root.update_idletasks()
        ImageGrab.grab(window=root.winfo_id()).save(a.output/'pending-restart.png')
        # C receives the new start only after the window observes OFF.
        until(lambda s:s.get('lifecycle')==3 and s.get('event_started',0)>=4)
        assert not window.pending_start
        window.ignition_off();until(lambda s:s.get('lifecycle')==5)
        off=until(lambda s:s.get('lifecycle')==0 and s.get('event_active')==0 and '熄火' in window.state.get() and window.rpm.get()=='0')
        root.update_idletasks()
        ImageGrab.grab(window=root.winfo_id()).save(a.output/'off-no-events.png')
        host=window.host;window.stop();until(lambda _:not window.running());window.save_take()
        paths=list((a.output/'takes').glob('*.vsltake.json'));assert len(paths)==1
        value=take.read(paths[0],window.bridge);played=replay(window.bridge,value)
        starts=[n for n in value['source_events'] if n['action']==1]
        assert [n['type'] for n in starts].count(1)==2 and [n['type'] for n in starts].count(2)==2
        assert played['source_events']==value['source_events']
        final=host.snapshot()
        for key,val in played['final_state'].items():assert final[key]==val,(key,final[key],val)
        catch_ends=[n for n in value['source_events'] if n['action']==2 and n['type']==2]
        assert len(catch_ends)==2 and all(n['reason']==1 for n in catch_ends)
        assert final['underflows']==0 and final['event_overflow']==final['event_log_lost']==final['event_rejected']==0
        verify(repo,binding)
        report=dict(schema='vsl.startup-abort-ui/1',result='passed',goal_complete=False,timbre_accepted=False,
            no_autoplay=True,UI_queues_restart_until_OFF=True,two_start_cycles=True,
            catch_ends_released=catch_ends,OFF_has_no_active_event=True,
            actual_take_notice_and_final_state_replay_exact=True,final_state=final,
            source_binding_sha256=sha(a.output/'source_binding.json'))
        take.save(a.output/'report.json',report);print(json.dumps(dict(result='passed',underflows=final['underflows'],cycles=2)))
    finally:
        window.stop();deadline=time.monotonic()+5
        while window.running() and time.monotonic()<deadline:pump()
        root.destroy()


if __name__=='__main__':
    try:main()
    except Exception:
        import traceback
        if '--output' in sys.argv:
            folder=Path(sys.argv[sys.argv.index('--output')+1]);folder.mkdir(parents=True,exist_ok=True)
            (folder/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
