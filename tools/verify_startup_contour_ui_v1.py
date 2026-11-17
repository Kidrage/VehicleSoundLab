"""Exercise V12 in an owned muted window, then close it; no app restart."""
import argparse
import ctypes as C
import json
from pathlib import Path
import time
import tkinter as tk
from unittest.mock import patch

from PIL import ImageGrab

from event_designer.package import write_json
from vehicle_controller import recipe,take
from vehicle_controller.ui import Window


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    data=Path('E:/VehicleSoundLab/references/analysis/startup_contour_v1/verification1')
    root=tk.Tk();window=Window(root,repo,output/'takes')
    observations=[]
    def pump():root.update();time.sleep(.01)
    def until(predicate,seconds=15):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            pump()
            state=window.host.snapshot() if window.host else {}
            if predicate(state):return state
        raise AssertionError(('timeout',state,window.message.get()))
    try:
        pump();assert not window.running()
        assert root.title().endswith('V12')
        preset=data/'V12-candidate/startup.recipe.json'
        with patch('vehicle_controller.ui.filedialog.askopenfilename',return_value=str(preset)):window.restore()
        assert window.message.get()=='参数已载入。',window.message.get()
        expected=json.loads(preset.read_text(encoding='utf-8'))
        assert window.control==expected['control']
        assert window.startup_response==expected['startup_response']
        saved=output/'UI-saved.preset.json'
        with patch('vehicle_controller.ui.filedialog.asksaveasfilename',return_value=str(saved)):window.save()
        roundtrip=json.loads(saved.read_text(encoding='utf-8'));recipe.validate(window.bridge,roundtrip)
        for key in ('startup_response','event_overrides','event_policy','source_effective_sha256'):
            assert roundtrip[key]==expected[key],key
        for key,value in expected['control'].items():
            if key!='input':assert roundtrip['control'][key]==value,key
        # controls() publishes a fresh simulated slip packet even while stopped.
        # Its monotonically increasing sequence and validity are not a stored
        # timbre parameter and must not be asserted equal to the imported packet.
        expected_signal=dict(expected['control']['input'],sequence=1,valid=4)
        assert roundtrip['control']['input']==expected_signal,roundtrip['control']['input']
        with patch('vehicle_controller.ui.filedialog.askopenfilename',return_value=str(data/'V11-original/startup.recipe.json')):window.restore()
        assert window.message.get()!='参数已载入。'
        assert window.control==expected['control'] and window.startup_response==expected['startup_response']
        window.muted.set(1)
        for variant in ('V12-original','V12-candidate'):
            recorded=take.read(data/variant/'lifecycle.vsltake.json',window.bridge)
            window.start(recorded);host=window.host;seen=[]
            until(lambda state:state.get('active') and state.get('frame',0)>0)
            deadline=time.monotonic()+14
            while window.running() and time.monotonic()<deadline:
                pump();state=host.snapshot()
                if state.get('active'):seen.append(state)
            assert not window.running(),variant
            final=host.snapshot();generated=host.take_snapshot()
            expected_final=json.loads((data/variant/'verification.json').read_text(encoding='utf-8'))['final_state']
            assert generated['source_events']==recorded['source_events'],variant
            assert final['underflows']==0,final
            assert all(state['shifts']==0 and state['operating']==0 and state['gear']==0 for state in seen),variant
            for key,value in expected_final.items():assert final[key]==value,(variant,key,final[key],value)
            observations.append(dict(variant=variant,frames=final['frame'],underflows=final['underflows'],
                                     notices_exact=True,final_state_exact=True,no_shift_states=True))
            print(json.dumps(observations[-1]),flush=True)
        window.tabs.select(window.drive);root.update()
        user=C.windll.user32
        user.GetAncestor.argtypes=[C.c_void_p,C.c_uint];user.GetAncestor.restype=C.c_void_p
        hwnd=user.GetAncestor(root.winfo_id(),2)
        title=C.create_unicode_buffer(512);user.GetWindowTextW.argtypes=[C.c_void_p,C.c_wchar_p,C.c_int]
        user.GetWindowTextW(hwnd,title,512);assert title.value.endswith('V12'),title.value
        ImageGrab.grab(window=hwnd).save(output/'V12-controller.png')
        write_json(output/'report.json',dict(result='passed',bridge_sha256=window.bridge.sha256,
            no_autoplay=True,preset_sound_parameters_restore_and_save_exact=True,
            saved_input_refresh=roundtrip['control']['input'],old_binary_preset_refused_without_mutation=True,
            cases=observations,audio_muted=True,own_window_closed=True,persistent_service_restarted=False,
            timbre_accepted=False))
    finally:
        window.stop();deadline=time.monotonic()+5
        while window.running() and time.monotonic()<deadline:pump()
        root.destroy()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
