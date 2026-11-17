"""Bounded owned muted V7 UI: edit, save/load, lifecycle, notices and replay."""
import argparse
import ctypes as C
from copy import deepcopy
import json
from pathlib import Path
import shutil
import time
from unittest.mock import patch

from vehicle_controller import take,recipe
from vehicle_scenarios.capture import replay
from startup_response_evidence_v1 import capture,verify


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    import tkinter as tk
    from PIL import ImageGrab
    from vehicle_controller.ui import Window
    repo=Path(__file__).resolve().parents[1]
    root=tk.Tk();window=Window(root,repo,a.output/'takes')
    binding=capture(repo,a.output,window.bridge.path);shutil.copy2(__file__,a.output/'executed_verification.py')
    def pump():root.update();time.sleep(.005)
    def until(predicate,seconds=8):
        deadline=time.monotonic()+seconds;state={}
        while time.monotonic()<deadline:
            pump();state=window.host.snapshot() if window.host else {}
            if state.get('error'):raise AssertionError(state)
            if predicate(state):return state
        raise AssertionError(('Window deadline',state))
    def screenshot(widget,name,title):
        widget.lift();widget.focus_force();widget.update();time.sleep(.1)
        user=C.windll.user32
        user.GetAncestor.argtypes=[C.c_void_p,C.c_uint];user.GetAncestor.restype=C.c_void_p
        user.GetWindowTextW.argtypes=[C.c_void_p,C.c_wchar_p,C.c_int]
        hwnd=user.GetAncestor(widget.winfo_id(),2);text=C.create_unicode_buffer(512)
        user.GetWindowTextW(hwnd,text,512);assert title in text.value,(title,text.value)
        ImageGrab.grab(window=hwnd).save(a.output/name)
    try:
        until(lambda _:True);assert root.title().endswith('V7') and not window.running()
        projects=Path('E:/VehicleSoundLab/designs/events')
        for name in ('773ad53ffd964fa18a7abfaf4aa2821b','462af3cefda441aba34886ecfc96dbae','028a56d636574ab1bb902a1d3479ac7e'):
            doc=json.loads((projects/name/'project.json').read_text(encoding='utf-8'))['document']
            path=a.output/(doc['kind']+'.parameters.json');take.save(path,doc);window.event_panel.import_profile(path)
        assert set(window.event_overrides)=={'crank','catch','afterfire'}
        window.tabs.select(window.events_page);window.edit_event_policy();panel=window.policy_panel
        assert len(panel.inputs)==10
        old=deepcopy(window.event_policy);panel.vars['afterfire_min_count'].set('4');panel.vars['afterfire_max_count'].set('2');panel.apply()
        assert window.policy_panel is panel and window.event_policy==old and '不能超过' in panel.message.get()
        panel.defaults();custom=dict(old,afterfire_min_count=3,afterfire_max_count=3,afterfire_delay_seconds=.04,
            afterfire_interval_min_seconds=.12,afterfire_interval_max_seconds=.12,afterfire_repeat_gain=.5,afterfire_cooldown_seconds=2.)
        for key,value in custom.items():panel.vars[key].set(f'{value:g}')
        screenshot(panel.root,'trigger-recipe.png','事件触发配方')
        panel.apply();assert window.event_policy==custom and window.policy_panel is None
        window.edit_event_policy();panel=window.policy_panel;panel.defaults()
        assert {key:float(var.get()) for key,var in panel.vars.items()}==window.bridge.event_policy_defaults
        panel.close();assert window.event_policy==custom
        saved=a.output/'custom.recipe.json'
        with patch('vehicle_controller.ui.filedialog.asksaveasfilename',return_value=str(saved)):window.save()
        document=json.loads(saved.read_text(encoding='utf-8'));recipe.validate(window.bridge,document)
        assert document['event_policy']==custom
        window.event_policy=deepcopy(old)
        with patch('vehicle_controller.ui.filedialog.askopenfilename',return_value=str(saved)):window.restore()
        assert window.event_policy==custom and set(window.event_overrides)=={'crank','catch','afterfire'}
        window.event_panel.enabled.set(1);window.muted.set(1);window.demo_button.invoke()
        until(lambda s:s.get('active') and s.get('frame',0)>4800)
        host=window.host;assert host.event_policy==custom and host.record['event_policy']==custom
        window.edit_event_policy();assert window.policy_panel is None and '请先停止' in window.message.get()
        until(lambda s:s.get('frame',0)>=17*48000,seconds=24)
        window.tabs.select(window.events_page);root.update_idletasks()
        screenshot(root,'event-status.png','驾驶与声源控制 V7')
        until(lambda _:not window.running(),seconds=23)
        final=host.snapshot();assert final['frame']==32*48000 and final['lifecycle']==0 and final['underflows']==0,final
        assert final['event_policy_stats']['opportunities']>=1 and final['event_policy_stats']['bursts_attempted']>=1,final
        window.save_take();paths=list((a.output/'takes').glob('*.vsltake.json'));assert len(paths)==1
        recorded=take.read(paths[0],window.bridge);assert recorded['event_policy']==custom
        starts=[n for n in recorded['source_events'] if n['type']==3 and n['action']==1]
        assert len(starts)==3 and starts[1]['frame']-starts[0]['frame']==5760 and starts[2]['frame']-starts[1]['frame']==5760,starts
        played=replay(window.bridge,recorded);assert played['source_events']==recorded['source_events']
        for key,value in played['final_state'].items():assert final[key]==value,(key,final[key],value)
        assert '缺音色' in window.event_panel.status.get()
        # Exercise the UI's saved-take adoption separately from the demo path.
        window.event_policy=deepcopy(old)
        with patch('vehicle_controller.ui.filedialog.askopenfilename',return_value=str(paths[0])):window.open_take()
        until(lambda s:s.get('active') and s.get('frame',0)>4800)
        assert window.event_policy==custom and window.host.event_policy==custom
        replay_host=window.host
        until(lambda _:not window.running(),seconds=40)
        again=replay_host.take_snapshot();assert again['source_events']==recorded['source_events'] and again['event_policy']==custom
        second=replay_host.snapshot();assert second['underflows']==0
        for key,value in played['final_state'].items():assert second[key]==value,(key,second[key],value)
        verify(repo,binding)
        report=dict(schema='vsl.event-policy-ui/1',result='passed',abi=window.bridge.abi(),muted=True,
            no_autoplay=True,ten_fields_editable=True,invalid_edit_preserves_configuration=True,
            reset_cancel_preserves_configuration=True,recipe_roundtrip=True,live_edit_refused=True,
            demo_adopts_policy=True,full_32s_cycle=True,automatic_starts=starts,final_state=final,
            take_and_varied_block_notices_state_exact=True,own_window_closed=True,
            saved_take_adopted_in_ui=True,second_full_32s_replay_exact=True,replay_final_state=second,
            scoped_E_physical_type_confirmed=False,goal_complete=False,timbre_accepted=False)
        take.save(a.output/'report.json',report);print(json.dumps(dict(result='passed',underflows=final['underflows'],starts=starts)))
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
