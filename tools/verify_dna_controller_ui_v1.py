"""Owned, bounded, muted V8 UI import/edit/recipe/lifecycle/take replay."""
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


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--fixture',type=Path,required=True);args=p.parse_args()
    out=args.output;out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,out/'executed_verification.py')
    import tkinter as tk
    from PIL import ImageGrab
    from vehicle_controller.ui import Window
    repo=Path(__file__).resolve().parents[1];root=tk.Tk();window=Window(root,repo,out/'takes')
    binding=capture(repo,out,window.bridge.path)
    def pump():root.update();time.sleep(.005)
    def until(predicate,seconds=8):
        deadline=time.monotonic()+seconds;state={}
        while time.monotonic()<deadline:
            pump();state=window.host.snapshot() if window.host else {}
            if state.get('error'):raise AssertionError(state)
            if predicate(state):return state
        raise AssertionError(('deadline',state))
    def screenshot(widget,name,title):
        widget.lift();widget.focus_force();widget.update();time.sleep(.1)
        user=C.windll.user32;user.GetAncestor.argtypes=[C.c_void_p,C.c_uint];user.GetAncestor.restype=C.c_void_p
        user.GetWindowTextW.argtypes=[C.c_void_p,C.c_wchar_p,C.c_int]
        hwnd=user.GetAncestor(widget.winfo_id(),2);text=C.create_unicode_buffer(512);user.GetWindowTextW(hwnd,text,512)
        assert title in text.value,(title,text.value);ImageGrab.grab(window=hwnd).save(out/name)
    try:
        until(lambda _:True);assert root.title().endswith('V8') and not window.running()
        window.tabs.select(window.tone);window.dna_button.invoke();panel=window.dna_panel
        assert panel and not panel.anchors
        panel.import_file(args.fixture/'v10.dnabank.json');assert len(panel.anchors)==1
        before=deepcopy(panel.anchors);panel.import_file(repo/'voices/dna_bank_v1/Warm Additive.model')
        assert panel.anchors==before and panel.message.get()
        panel.vars['seed'].set('0');panel.apply();assert window.dna_bank is None and window.dna_panel is panel
        panel.vars['seed'].set('48271');panel.vars['detail'].set('.56')
        bank=panel.configuration();screenshot(panel.root,'dna-editor.png','工作台DNA')
        package=out/'editor.dnabank.json'
        with patch('vehicle_controller.dna_panel.filedialog.asksaveasfilename',return_value=str(package)):panel.export()
        assert dna.read(package)==bank
        panel.apply();assert window.dna_bank==bank and window.features==0 and window.dna_panel is None
        assert window.vars['detail'].get()==.56 and window.event_panel.enabled.get()==0
        for key in ('coherent_low_gain','resonant_gain','residual_gain','idle_mix','startup_gain','catch_gain'):
            assert window.widgets[key][0].instate(['disabled'])
        saved=out/'editor.recipe.json'
        with patch('vehicle_controller.ui.filedialog.asksaveasfilename',return_value=str(saved)):window.save()
        doc=json.loads(saved.read_text(encoding='utf-8'));recipe.validate(window.bridge,doc);assert doc['dna_bank']==bank
        window.load(0);assert window.dna_bank is None
        with patch('vehicle_controller.ui.filedialog.askopenfilename',return_value=str(saved)):window.restore()
        assert window.dna_bank==bank
        bad=deepcopy(doc);bad['dna_bank']['detail']=.1;take.save(out/'tampered.recipe.json',bad)
        control=deepcopy(window.control)
        with patch('vehicle_controller.ui.filedialog.askopenfilename',return_value=str(out/'tampered.recipe.json')):window.restore()
        assert window.dna_bank==bank and window.control==control
        window.muted.set(1);screenshot(root,'tone-panel.png','驾驶与声源控制 V8')
        # Independent event parameters are explicitly adopted, then enabled.
        for name in ('773ad53ffd964fa18a7abfaf4aa2821b','462af3cefda441aba34886ecfc96dbae'):
            event=json.loads((Path('E:/VehicleSoundLab/designs/events')/name/'project.json').read_text(encoding='utf-8'))['document']
            file=out/(event['kind']+'.json');take.save(file,event);window.event_panel.import_profile(file)
        window.event_panel.enabled.set(1);window.demo_button.invoke()
        until(lambda s:s.get('active') and s.get('frame',0)>4800)
        host=window.host;assert host.dna_bank==bank and host.record['dna_bank']==bank
        window.edit_dna();assert window.dna_panel is None and '请先停止' in window.message.get()
        until(lambda _:not window.running(),seconds=40)
        final=host.snapshot();assert final['frame']==32*48000 and final['lifecycle']==0 and final['underflows']==0,final
        assert final['shifts']>0 and final['event_started']>=2,final
        window.save_take();files=list((out/'takes').glob('*.vsltake.json'));assert len(files)==1
        recorded=take.read(files[0],window.bridge);assert recorded['dna_bank']==bank
        played=replay(window.bridge,recorded);assert played['source_events']==recorded['source_events']
        for key,value in played['final_state'].items():assert final[key]==value,(key,final[key],value)
        window.load(0);assert window.dna_bank is None
        with patch('vehicle_controller.ui.filedialog.askopenfilename',return_value=str(files[0])):window.open_take()
        until(lambda s:s.get('active') and s.get('frame',0)>4800)
        assert window.dna_bank==bank and window.host.dna_bank==bank
        again=window.host;until(lambda _:not window.running(),seconds=40)
        assert again.take_snapshot()['source_events']==recorded['source_events'] and again.snapshot()['underflows']==0
        for key,value in played['final_state'].items():assert again.snapshot()[key]==value,(key,again.snapshot()[key],value)
        window.tabs.select(window.tone);window.edit_dna();window.dna_panel.catalog()
        assert window.dna_bank is None and window.features!=0
        verify(repo,binding)
        take.save(out/'report.json',dict(schema='vsl.dna-controller-ui/1',result='passed',abi=8,
            muted=True,no_autoplay=True,import_edit_export=True,invalid_preserves_state=True,
            recipe_roundtrip=True,tampered_recipe_transactional=True,optional_controls_disabled=True,
            driver_uses_authored_DNA=True,full_32s_cycle=True,saved_take_UI_32s_replay=True,
            recorded_notices_state_exact=True,underflows=final['underflows'],final_state=final,
            catalog_restore=True,own_window_closed=True,new_timbre_accepted=False,goal_complete=False))
        print(json.dumps(dict(result='passed',underflows=final['underflows'])),flush=True)
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
