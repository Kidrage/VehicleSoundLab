"""Owned bounded muted V9 editor, lifecycle, saved take and state telemetry."""
import argparse
from copy import deepcopy
import ctypes as C
import json
from pathlib import Path
import shutil
import time
from unittest.mock import patch
from vehicle_controller import dna_bank as dna,take,recipe
from vehicle_scenarios.capture import replay
from startup_response_evidence_v1 import capture,verify
from verify_state_dna_controller_v1 import fixtures


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    out=args.output;out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,out/'executed_verification.py')
    import tkinter as tk
    from PIL import ImageGrab
    from vehicle_controller.ui import Window
    from vehicle_controller.dna_panel import STATE_LABELS
    repo=Path(__file__).resolve().parents[1];root=tk.Tk();window=Window(root,repo,out/'takes')
    binding=capture(repo,out,window.bridge.path)
    fixture=out/'fixtures';fixture.mkdir();base,bank=fixtures(repo,fixture);observed=set()
    def pump():
        root.update();time.sleep(.005)
        if window.host:
            state=window.host.snapshot()
            if state.get('error'):raise AssertionError(state)
            if state.get('lifecycle')==4:
                observed.update(k for k,w in enumerate(state.get('dna_state',{}).get('weight',[])) if w>.95)
    def until(predicate,seconds=8):
        deadline=time.monotonic()+seconds;state={}
        while time.monotonic()<deadline:
            pump();state=window.host.snapshot() if window.host else {}
            if predicate(state):return state
        raise AssertionError(('deadline',state))
    def screenshot(widget,name,title):
        widget.lift();widget.focus_force();widget.update();time.sleep(.1)
        user=C.windll.user32;user.GetAncestor.argtypes=[C.c_void_p,C.c_uint];user.GetAncestor.restype=C.c_void_p
        user.GetWindowTextW.argtypes=[C.c_void_p,C.c_wchar_p,C.c_int]
        hwnd=user.GetAncestor(widget.winfo_id(),2);text=C.create_unicode_buffer(512);user.GetWindowTextW(hwnd,text,512)
        assert title in text.value,(title,text.value)
        ImageGrab.grab(window=hwnd).save(out/name)
    try:
        until(lambda _:True);assert root.title().endswith('V9') and not window.running()
        window.tabs.select(window.tone);window.dna_button.invoke();panel=window.dna_panel
        take.save(fixture/'base.dnabank.json',base);panel.import_file(fixture/'base.dnabank.json')
        for state in dna.STATES:
            panel.state.set(STATE_LABELS[state]);panel.refresh();panel.import_file(fixture/(state+'.model'))
            assert len(panel.anchors)==1 and panel.anchors[0]['name']==state
        expected=panel.configuration();assert set(expected['states'])==set(dna.STATES)
        before=deepcopy(panel.groups);panel.import_file(repo/'voices/dna_bank_v1/Warm Additive.model')
        assert panel.groups==before and '分音' in panel.message.get()
        panel.vars['transition_seconds'].set('.001');panel.apply()
        assert window.dna_bank is None and window.dna_panel is panel
        panel.vars['transition_seconds'].set('.12')
        panel.state.set(STATE_LABELS['idle']);panel.refresh();screenshot(panel.root,'state-editor.png','工作台DNA')
        panel.clear();assert 'idle' not in panel.configuration().get('states',{})
        panel.import_file(fixture/'idle.model');expected=panel.configuration()
        package=out/'editor.dnabank.json'
        with patch('vehicle_controller.dna_panel.filedialog.asksaveasfilename',return_value=str(package)):panel.export()
        assert dna.read(package)==expected
        panel.apply();assert window.dna_bank==expected and window.features==0 and window.dna_panel is None
        window.edit_dna();panel=window.dna_panel;panel.import_file(package)
        assert panel.configuration()==expected;panel.apply()
        saved=out/'editor.recipe.json'
        with patch('vehicle_controller.ui.filedialog.asksaveasfilename',return_value=str(saved)):window.save()
        document=json.loads(saved.read_text(encoding='utf-8'));recipe.validate(window.bridge,document)
        window.load(0)
        with patch('vehicle_controller.ui.filedialog.askopenfilename',return_value=str(saved)):window.restore()
        assert window.dna_bank==expected
        for name in ('773ad53ffd964fa18a7abfaf4aa2821b','462af3cefda441aba34886ecfc96dbae'):
            event=json.loads((Path('E:/VehicleSoundLab/designs/events')/name/'project.json').read_text(encoding='utf-8'))['document']
            file=out/(event['kind']+'.json');take.save(file,event);window.event_panel.import_profile(file)
        window.event_panel.enabled.set(1);window.muted.set(1);window.demo_button.invoke()
        until(lambda s:s.get('active') and s.get('frame',0)>4800)
        host=window.host;assert host.dna_bank==expected and host.record['dna_bank']==expected
        until(lambda s:s.get('frame',0)>4*48000)
        assert '当前DNA' in window.dna_status.get()
        for size in ('1020x800','920x760'):
            root.geometry(size);root.update();pump()
            assert window.mute_box.winfo_rooty()+window.mute_box.winfo_height()<=window.tone.winfo_rooty()+window.tone.winfo_height()
        screenshot(root,'state-minimum.png','驾驶与声源控制 V9')
        root.geometry('1020x800');root.update()
        screenshot(root,'state-live.png','驾驶与声源控制 V9')
        window.edit_dna();assert window.dna_panel is None and '请先停止' in window.message.get()
        until(lambda _:not window.running(),seconds=40)
        final=host.snapshot();assert final['frame']==32*48000 and final['lifecycle']==0 and final['underflows']==0,final
        assert {1,2,3}<=observed,observed
        window.save_take();files=list((out/'takes').glob('*.vsltake.json'));assert len(files)==1
        recorded=take.read(files[0],window.bridge);assert recorded['dna_bank']==expected
        played=replay(window.bridge,recorded);assert played['source_events']==recorded['source_events']
        for key,value in played['final_state'].items():assert final[key]==value,(key,final[key],value)
        window.load(0)
        with patch('vehicle_controller.ui.filedialog.askopenfilename',return_value=str(files[0])):window.open_take()
        until(lambda s:s.get('active') and s.get('frame',0)>4800)
        assert window.dna_bank==expected
        again=window.host;until(lambda _:not window.running(),seconds=40)
        assert again.take_snapshot()['source_events']==recorded['source_events'] and again.snapshot()['underflows']==0
        for key,value in played['final_state'].items():assert again.snapshot()[key]==value,(key,again.snapshot()[key],value)
        window.tabs.select(window.tone);screenshot(root,'state-restored.png','驾驶与声源控制 V9')
        window.edit_dna();window.dna_panel.catalog();assert window.dna_bank is None
        verify(repo,binding)
        take.save(out/'report.json',dict(schema='vsl.state-dna-controller-ui/1',result='passed',abi=9,
            muted=True,no_autoplay=True,state_editor_import_export=True,invalid_preserves_state=True,
            missing_state_fallback_edit=True,recipe_roundtrip=True,full_32s_cycle=True,
            state_telemetry_observed=sorted(observed),saved_take_UI_32s_replay=True,
            recorded_notices_state_exact=True,underflows=final['underflows'],final_state=final,
            catalog_restore=True,own_window_closed=True,new_timbre_accepted=False,goal_complete=False))
        print(json.dumps(dict(result='passed',states=sorted(observed))),flush=True)
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
