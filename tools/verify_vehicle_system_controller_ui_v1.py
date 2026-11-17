"""Import the browser's single vehicle file in an owned muted V9 window."""
import argparse
from copy import deepcopy
import ctypes as C
import json
from pathlib import Path
import shutil
import time
import traceback
from unittest.mock import patch
from event_authoring.contract import KINDS
from vehicle_controller import take, recipe
from vehicle_scenarios.capture import replay
from startup_response_evidence_v1 import capture, verify
from research_archive_v1 import sha, save, load


def run(out,preset):
    out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,out/'executed_verification.py')
    shutil.copy2(preset,out/'downloaded.preset.json');expected=load(preset)
    import tkinter as tk
    from PIL import ImageGrab
    from vehicle_controller.ui import Window
    repo=Path(__file__).resolve().parents[1];root=tk.Tk();window=Window(root,repo,out/'takes')
    binding=capture(repo,out,window.bridge.path);observed=set();progress=0
    def pump():
        nonlocal progress
        root.update();time.sleep(.005)
        if window.host:
            state=window.host.snapshot()
            if state.get('error'):raise AssertionError(state)
            if state.get('lifecycle')==4:
                observed.update(k for k,w in enumerate(state.get('dna_state',{}).get('weight',[])) if w>.95)
            frame=state.get('frame',0)
            if frame>=progress+4*48000:
                progress=frame;print(json.dumps(dict(generated_seconds=frame/48000,replaying=window.replaying)),flush=True)
    def until(predicate,seconds=8):
        deadline=time.monotonic()+seconds;state={}
        while time.monotonic()<deadline:
            pump();state=window.host.snapshot() if window.host else {}
            if predicate(state):return state
        raise AssertionError(('deadline',state))
    def screenshot(name):
        root.lift();root.focus_force();root.update();time.sleep(.1)
        user=C.windll.user32;user.GetAncestor.argtypes=[C.c_void_p,C.c_uint];user.GetAncestor.restype=C.c_void_p
        user.GetWindowTextW.argtypes=[C.c_void_p,C.c_wchar_p,C.c_int]
        hwnd=user.GetAncestor(root.winfo_id(),2);title=C.create_unicode_buffer(512);user.GetWindowTextW(hwnd,title,512)
        assert '驾驶与声源控制 V9' in title.value,title.value
        ImageGrab.grab(window=hwnd).save(out/name)
    try:
        until(lambda _:True);assert not window.running()
        with patch('vehicle_controller.ui.filedialog.askopenfilename',return_value=str(preset)):window.restore()
        assert window.message.get()=='参数已载入。',window.message.get()
        assert window.dna_bank==expected['dna_bank'] and window.event_overrides==expected['event_overrides']
        assert window.startup_response==expected['startup_response'] and window.event_policy==expected['event_policy']
        assert window.control==expected['control'] and window.mode.get()==expected['mode']
        assert window.preset.get()=='工作台 DNA · '+expected['dna_bank']['name']
        assert window.event_panel.available_mask()==127 and all('disabled' not in b.state() for b in window.event_panel.buttons)
        saved=out/'UI-saved.preset.json'
        with patch('vehicle_controller.ui.filedialog.asksaveasfilename',return_value=str(saved)):window.save()
        roundtrip=load(saved);recipe.validate(window.bridge,roundtrip)
        for key in ('dna_bank','startup_response','event_policy','event_overrides','source_effective_sha256'):
            assert roundtrip[key]==expected[key],key
        for key,value in expected['control'].items():
            if key!='input':assert roundtrip['control'][key]==value,key
        bad=deepcopy(expected);bad['event_policy']['afterfire_delay_seconds']=.123;save(out/'invalid.preset.json',bad)
        before=(deepcopy(window.dna_bank),deepcopy(window.event_overrides),deepcopy(window.event_policy))
        with patch('vehicle_controller.ui.filedialog.askopenfilename',return_value=str(out/'invalid.preset.json')):window.restore()
        assert before==(window.dna_bank,window.event_overrides,window.event_policy)
        assert window.message.get()!='参数已载入。'
        window.tabs.select(window.events_page);screenshot('imported-events.png')
        window.muted.set(1);window.demo_button.invoke()
        until(lambda s:s.get('active') and s.get('frame',0)>4800);host=window.host
        assert host.dna_bank==expected['dna_bank'] and host.record['event_overrides']==expected['event_overrides']
        until(lambda s:s.get('frame',0)>4*48000);screenshot('live-events.png')
        until(lambda _:not window.running(),seconds=40)
        final=host.snapshot();assert final['frame']==32*48000 and final['lifecycle']==0 and final['underflows']==0,final
        assert {1,2,3}<=observed,observed
        window.save_take();files=list((out/'takes').glob('*.vsltake.json'));assert len(files)==1
        recorded=take.read(files[0],window.bridge)
        for key in ('dna_bank','startup_response','event_policy','event_overrides'):
            assert recorded[key]==expected[key],key
        starts={kind:sum(n['action']==1 and n['type']==i for n in recorded['source_events']) for i,kind in enumerate(KINDS)}
        assert all(starts.values()) and starts['afterfire']==3,starts
        played=replay(window.bridge,recorded);assert played['source_events']==recorded['source_events']
        for key,value in played['final_state'].items():assert final[key]==value,(key,final[key],value)
        window.load(0);progress=0
        assert window.preset.get()==window.bridge.catalog[0]['name']
        with patch('vehicle_controller.ui.filedialog.askopenfilename',return_value=str(files[0])):window.open_take()
        until(lambda s:s.get('active') and s.get('frame',0)>4800);again=window.host
        until(lambda _:not window.running(),seconds=40)
        assert again.take_snapshot()['source_events']==recorded['source_events'] and again.snapshot()['underflows']==0
        for key,value in played['final_state'].items():assert again.snapshot()[key]==value,(key,again.snapshot()[key],value)
        window.tabs.select(window.drive);screenshot('restored-drive.png');verify(repo,binding)
        save(out/'report.json',dict(result='passed',downloaded_preset_sha256=sha(preset),bridge_sha256=window.bridge.sha256,
            one_file_restore_all_settings=True,no_autoplay=True,invalid_preserves_state=True,save_roundtrip=True,
            full_32s_cycle=True,event_start_counts=starts,state_weights_observed=sorted(observed),
            saved_take_32s_UI_replay=True,source_notices_final_state_exact=True,underflows=final['underflows'],
            own_window_closed=True,muted=True,new_timbre_accepted=False,goal_complete=False))
        print(json.dumps(dict(result='passed',event_start_counts=starts)),flush=True)
    finally:
        window.stop();deadline=time.monotonic()+5
        while window.running() and time.monotonic()<deadline:pump()
        root.destroy()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--preset',type=Path,required=True);args=p.parse_args()
    try:run(args.output,args.preset)
    except Exception:
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
