"""Actual muted Tk/WinMM app, native burst triggering and take replay."""
import argparse
import json
from pathlib import Path
import time
import tkinter as tk
from PIL import ImageGrab
from vehicle_controller.ui import Window
from vehicle_controller import take

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];root=tk.Tk();w=Window(root,repo,a.output/'takes');w.muted.set(1)
    def advance(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:root.update();time.sleep(.005)
    def wait_for(test,seconds=8):
        end=time.monotonic()+seconds
        while not test() and time.monotonic()<end:
            advance(.02)
            assert not w.host.snapshot().get('error'),w.host.snapshot()
        assert test(),w.host.snapshot()
    report={}
    try:
        advance(.2);assert 'V20' in root.title() and w.controls()['startup_gain']==.5
        assert w.event_policy['afterfire_max_count']==10 and w.event_overrides['afterfire']['reference_evidence']['source_id']=='G'
        w.tabs.select(w.events_page);advance(.1);w.event_panel.buttons[3].invoke()
        wait_for(lambda:w.host.snapshot().get('event_started',0)>=6)
        advance(.6);manual=w.host.snapshot();assert 6<=manual['event_started']<=10 and manual['lifecycle']==0
        assert manual['underflows']==0 and manual['event_overflow']==0,manual
        ImageGrab.grab(window=root.winfo_id()).save(a.output/'App-V20-events.png')
        w.stop();advance(.2);w.save_take();assert not w.last_error,w.last_error
        path=next((a.output/'takes').glob('*.vsltake.json'));record=take.read(path,w.bridge)
        # Host completion can precede Tk's next 40ms refresh. Wait for the UI
        # to leave replay and re-enable Start before invoking the next action.
        w.start(record);wait_for(lambda:not w.running() and not w.replaying and not w.start_button.instate(['disabled']),record['frames']/48000+6)
        replay=w.host.snapshot();assert replay['event_started']==manual['event_started'] and replay['underflows']==0,replay
        w.load(0);w.automatic.set(0);w.gear.set(0);w.tabs.select(w.drive);w.start_button.invoke()
        wait_for(lambda:w.host.snapshot().get('lifecycle')==4)
        w.vars['throttle'].set(.95);advance(1.6);w.vars['throttle'].set(0);advance(1.3)
        automatic=w.host.snapshot();assert 6<=automatic['event_started']<=10,automatic
        assert automatic['underflows']==0 and not automatic['event_overflow'],automatic
        w.stop();advance(.2)
        w.tabs.select(w.dna_page);advance(.2)
        ImageGrab.grab(window=root.winfo_id()).save(a.output/'App-V20-DNA.png')
        w.edit_event_policy();advance(.1)
        assert float(w.policy_panel.inputs['afterfire_max_count'].cget('to'))==12
        w.policy_panel.close()
        # The main UI still loads the exact old binary/recipe for old takes.
        frozen=Window(tk.Toplevel(root),repo,a.output/'frozen-takes',repo/'build-vehicle-source-v16/bin/Release/vsl_source_bridge.dll')
        assert 'V19' in frozen.root.title() and frozen.event_policy['afterfire_max_count']==2
        frozen.root.destroy()
        report=dict(schema='vsl.coast-afterfire-ui/1',muted=True,manual=manual,replay=replay,
                    automatic=automatic,queue_limit=12,unchanged_voice_limit=4,frozen_v19_defaults_preserved=True,
                    title=root.title(),library_sha256=w.bridge.sha256)
    finally:w.stop();advance(.2);root.destroy()
    (a.output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
