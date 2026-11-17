"""Owned muted controller: real idle controls, preset roundtrip and36s replay."""
import argparse
import ctypes as C
from pathlib import Path
import shutil
import time
import tkinter as tk
from unittest.mock import patch

from PIL import ImageGrab

from research_archive_v1 import load, save
from vehicle_controller import recipe, take
from vehicle_controller.ui import Window


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,args.output/'executed_verification.py')
    expected = load(args.evidence/'report.json')
    assert expected['result'] == 'passed'
    root = tk.Tk()
    window = Window(root,Path(__file__).resolve().parents[1],args.output/'takes')
    report = dict(result='running',audio_muted=True,own_window_closed=False,
        persistent_service_restarted=False,goal_complete=False,timbre_accepted=False)
    def pump():
        root.update();time.sleep(.005)
    def screenshot(file):
        user = C.windll.user32
        user.GetAncestor.argtypes=[C.c_void_p,C.c_uint];user.GetAncestor.restype=C.c_void_p
        ImageGrab.grab(window=user.GetAncestor(root.winfo_id(),2)).save(args.output/file)
    try:
        pump()
        original = load(args.evidence/'controller-preset.json')
        with patch('vehicle_controller.ui.filedialog.askopenfilename',return_value=str(args.evidence/'controller-preset.json')):
            window.restore()
        assert window.message.get() == '参数已载入。'
        assert window.preset_box.current() == original['catalog'] == 0
        for key,value in [('idle_mix',1.),('idle_motion',.5),('idle_detail',1.)]:
            assert not window.widgets[key][0].instate(['disabled']) and window.vars[key].get() == value
        saved = args.output/'saved.preset.json'
        with patch('vehicle_controller.ui.filedialog.asksaveasfilename',return_value=str(saved)):
            window.save()
        restored = load(saved)
        recipe.validate(window.bridge,restored)
        for key in ('event_overrides','event_policy','startup_response','dna_bank','source_effective_sha256'):
            assert restored[key] == original[key],key
        for key in original['control']:
            if key != 'input':assert restored['control'][key] == original['control'][key],key
        window.tabs.select(window.tone);pump();screenshot('idle-controls.png')
        window.muted.set(1)
        value = take.read(args.evidence/'idle_layer/lifecycle.vsltake.json',window.bridge)
        window.start(value)
        deadline = time.monotonic()+55
        heard_states = set()
        max_idle = 0.
        while window.running() and time.monotonic() < deadline:
            pump()
            state = window.host.snapshot()
            heard_states.add((state.get('lifecycle'),state.get('operating')))
            max_idle = max(max_idle,state.get('idle_weight',0.))
        assert not window.running(),'owned36s replay deadline'
        state = window.host.snapshot()
        assert state['frame'] == value['frames'] and state['underflows'] == 0 and max_idle > .99,state
        for key,target in expected['measurements']['idle_layer']['final_state'].items():
            assert state[key] == target,(key,state[key],target)
        actual = window.host.take_snapshot()
        assert actual['source_events'] == value['source_events'] and actual['event_overrides'] == value['event_overrides']
        window.tabs.select(window.drive);pump();screenshot('controller.png')
        report.update(result='passed',preset_roundtrip_exact=True,idle_controls_enabled=True,
            frames=state['frame'],underflows=0,idle_weight_max=max_idle,notices_state_exact=True,
            observed_states=[list(x) for x in sorted(heard_states,key=str)],bridge_sha256=window.bridge.sha256)
    except Exception as error:
        report.update(result='failed',error=repr(error));raise
    finally:
        window.stop();deadline=time.monotonic()+5
        while window.running() and time.monotonic()<deadline:pump()
        root.destroy();report['own_window_closed']=True;save(args.output/'report.json',report)


if __name__ == '__main__':
    main()
