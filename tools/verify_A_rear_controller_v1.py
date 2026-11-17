"""Own muted native window: new startup preset, roundtrip and two8s replays."""
import argparse
import ctypes as C
from pathlib import Path
import shutil
import time
import tkinter as tk
from unittest.mock import patch

from PIL import ImageGrab

from research_archive_v1 import load,save,sha
from vehicle_controller import recipe,take
from vehicle_controller.ui import Window


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,args.output/'executed_verification.py')
    repo=Path(__file__).resolve().parents[1]
    expected=load(args.evidence/'report.json');assert expected['result']=='passed'
    root=tk.Tk();window=Window(root,repo,args.output/'takes')
    report=dict(result='running',goal_complete=False,timbre_accepted=False,audio_muted=True,
        own_window_closed=False,persistent_service_restarted=False)
    def pump():root.update();time.sleep(.005)
    def screenshot(name):
        user=C.windll.user32
        user.GetAncestor.argtypes=[C.c_void_p,C.c_uint];user.GetAncestor.restype=C.c_void_p
        hwnd=user.GetAncestor(root.winfo_id(),2)
        ImageGrab.grab(window=hwnd).save(args.output/name)
    try:
        pump();assert not window.running() and window.bridge.sha256==expected['bridge_sha256']
        preset=args.evidence/'controller-preset.json'
        with patch('vehicle_controller.ui.filedialog.askopenfilename',return_value=str(preset)):window.restore()
        assert window.message.get()=='参数已载入。',window.message.get()
        original=load(preset)
        assert window.event_overrides==original['event_overrides']
        saved=args.output/'UI-saved.preset.json'
        with patch('vehicle_controller.ui.filedialog.asksaveasfilename',return_value=str(saved)):window.save()
        restored=load(saved);recipe.validate(window.bridge,restored)
        for key in ('event_overrides','event_policy','startup_response','dna_bank','source_effective_sha256'):
            assert restored[key]==original[key],key
        for key in original['control']:
            if key!='input':assert restored['control'][key]==original['control'][key],key
        window.tabs.select(window.events_page);pump();screenshot('startup-events.png')
        window.muted.set(1);report['cases']=[]
        for name in ('early','pair25'):
            value=take.read(args.evidence/name/'lifecycle.vsltake.json',window.bridge)
            window.start(value)
            deadline=time.monotonic()+20
            while window.running() and time.monotonic()<deadline:pump()
            assert not window.running(),'owned replay timeout'
            host=window.host;state=host.snapshot()
            assert state['frame']==value['frames'] and state['underflows']==0,state
            for key,target in expected['variants'][name]['measurement']['final_state'].items():
                assert state[key]==target,(name,key,state[key],target)
            actual=host.take_snapshot()
            assert actual['source_events']==value['source_events']
            assert actual['event_overrides']==value['event_overrides']
            report['cases'].append(dict(name=name,frames=state['frame'],underflows=0,
                notices_state_exact=True,event_overrides_exact=True))
            print(name,'owned muted native replay passed',flush=True)
        window.tabs.select(window.drive);pump();screenshot('startup-controller.png')
        bindings=load(args.evidence.parent/'selection1/runtime.json')
        assert len(bindings)==459 and all(sha(repo/name)==digest for name,digest in bindings.items())
        report.update(result='passed',parameter_roundtrip_exact=True,runtime_voice_files_unchanged=459,
            bridge_sha256=window.bridge.sha256)
    except Exception as error:report.update(result='failed',error=repr(error));raise
    finally:
        window.stop();deadline=time.monotonic()+5
        while window.running() and time.monotonic()<deadline:pump()
        root.destroy();report['own_window_closed']=True;save(args.output/'report.json',report)


if __name__=='__main__':main()
