"""Real-material override through preset import, native replay and bounded UI."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('review',type=Path)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    import tkinter as tk
    from PIL import ImageGrab
    from vehicle_controller.ui import Window
    from vehicle_controller import take
    from vehicle_scenarios.capture import replay
    from startup_response_evidence_v1 import capture,verify,sha
    repo=Path(__file__).resolve().parents[1];binding=capture(repo,a.output)
    import shutil
    shutil.copy2(__file__,a.output/'executed_verification.py')
    root=tk.Tk();window=Window(root,repo,a.output/'takes')
    def pump(seconds):
        until=time.monotonic()+seconds
        while time.monotonic()<until:root.update();time.sleep(.005)
    report=dict(schema='vsl.exhaust-return-verification/1',goal_complete=False,timbre_accepted=False,
        physical_identity_confirmed=False,method='Actual local event import, recipe, C take/variable blocks; own muted Tk/WinMM.')
    try:
        pump(.1);assert not window.running()
        window.tabs.select(window.events_page)
        window.event_panel.import_profile(a.review/'event-profile.json');pump(.1)
        assert 'afterfire' in window.event_overrides
        assert '1.2' in window.event_panel.model_info.get() and '尚未确认' in window.event_panel.model_info.get()
        assert window.event_panel.buttons[3].instate(['!disabled'])
        ImageGrab.grab(window=root.winfo_id()).save(a.output/'imported-event.png')
        with patch('vehicle_controller.ui.filedialog.askopenfilename',return_value=str(a.review/'controller-preset.json')):window.restore()
        assert window.loaded==1 and window.event_overrides['afterfire']['parameters']
        reference=take.read(a.review/'drive_on.vsltake.json',window.bridge)
        expected=deepcopy(window.event_overrides)
        window.muted.set(1);window.start(reference);pump(.2)
        assert window.running() and window.replaying and window.host.event_overrides==expected
        deadline=time.monotonic()+18;snapshots=[];screen=False;last=-1
        while window.running() and time.monotonic()<deadline:
            pump(.02);state=window.host.snapshot()
            if state.get('error'):raise AssertionError(state)
            seconds=state.get('frame',0)/48000
            if seconds//2>last:last=seconds//2;snapshots.append(state)
            if seconds>4 and not screen:
                ImageGrab.grab(window=root.winfo_id()).save(a.output/'automatic-return.png');screen=True
        pump(.1);assert not window.running() and screen
        final=window.host.snapshot();assert final['frame']==384000 and final['overruns']==2 and not final.get('error')
        assert final['event_peak']<=4 and final['event_overflow']==final['event_log_lost']==final['event_rejected']==0
        window.save_take();paths=list((a.output/'takes').glob('*.vsltake.json'));assert len(paths)==1
        saved=take.read(paths[0],window.bridge);assert saved['event_overrides']==expected
        assert saved['source_events']==reference['source_events']
        actual=replay(window.bridge,saved);original=replay(window.bridge,reference,block_pattern=(480,))
        assert actual['pcm_sha256']==original['pcm_sha256']
        assert actual['source_events']==saved['source_events']
        for key,value in actual['final_state'].items():assert final[key]==value,(key,final[key],value)
        verify(repo,binding)
        report.update(result='passed',limited_scope_visible=True,unconfirmed_type_visible=True,import_and_recipe_roundtrip=True,
            native_variable_block_replay_exact=True,actual_host_events_and_final_state_exact=True,no_autoplay=True,
            automatic_afterfire_starts=sum(e['type']==3 and e['action']==1 for e in saved['source_events']),
            final_state=final,snapshots=snapshots,source_binding_sha256=sha(a.output/'source_binding.json'))
        take.save(a.output/'report.json',report)
    finally:
        window.stop();deadline=time.monotonic()+4
        while window.running() and time.monotonic()<deadline:pump(.02)
        root.destroy()
    print(json.dumps(dict(result=report['result'],starts=report['automatic_afterfire_starts'],underflows=report['final_state']['underflows'])))


if __name__=='__main__':
    try:main()
    except Exception:
        import traceback
        if '--output' in sys.argv:
            folder=Path(sys.argv[sys.argv.index('--output')+1]);folder.mkdir(parents=True,exist_ok=True)
            (folder/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
