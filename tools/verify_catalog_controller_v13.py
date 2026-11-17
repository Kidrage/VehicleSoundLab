"""Actual Complete Flow button, strict preset loading, save and36s device replay."""
import argparse
from copy import deepcopy
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, out/'executed_verification.py')
    expected = load(args.evidence/'report.json')
    assert expected['result'] == 'passed'
    root = tk.Tk()
    window = Window(root, Path(__file__).resolve().parents[1], out/'takes')
    report = dict(result='running', audio_muted=True, own_window_closed=False,
        persistent_service_restarted=False, goal_complete=False, timbre_accepted=False)
    def pump():
        root.update()
        time.sleep(.005)
    def screenshot(name):
        user = C.windll.user32
        user.GetAncestor.argtypes = [C.c_void_p,C.c_uint]
        user.GetAncestor.restype = C.c_void_p
        ImageGrab.grab(window=user.GetAncestor(root.winfo_id(),2)).save(out/name)
    def snapshot():
        return deepcopy(dict(selection=window.loaded, control=window.control,
            variables={key:value.get() for key,value in window.vars.items()}, mode=window.mode.get(),
            profiles=window.event_overrides, response=window.startup_response,
            policy=window.event_policy, dna=window.dna_bank))
    def complete():
        deadline = time.monotonic()+55
        observed = []
        while window.running():
            pump()
            state = window.host.snapshot()
            assert not state.get('error'), state
            if 'frame' in state:
                observed.append((state['frame'],state['idle_weight']))
            assert time.monotonic() < deadline, state
        # Wait for the scheduled40ms UI tick to adopt the terminal host state.
        deadline = time.monotonic()+1
        while window.replaying or window.demo_button.instate(['disabled']):
            pump()
            assert time.monotonic() < deadline
        assert window.state.get() == '熄火 · 监听停止'
        state = window.host.snapshot()
        assert not state.get('error') and state['frame'] == 36*48000
        assert state['underflows'] == 0, state
        for key,target in expected['cases']['idle_layer']['final_state'].items():
            assert state[key] == target, (key,state[key],target)
        assert any(3*48000 < frame < 5.5*48000 and weight > .99 for frame,weight in observed)
        assert any(31*48000 < frame < 33.5*48000 and weight > .99 for frame,weight in observed)
        return state, window.host.take_snapshot()
    try:
        window.muted.set(1)
        preset_path = args.evidence/'controller-preset.json'
        with patch('vehicle_controller.ui.filedialog.askopenfilename',return_value=str(preset_path)):
            window.restore()
        assert window.message.get() == '参数已载入。'
        preset = load(preset_path)
        assert window.loaded == 0 and window.event_overrides == preset['event_overrides']
        for key in ('idle_mix','idle_motion','idle_detail'):
            assert not window.widgets[key][0].instate(['disabled'])
        before = snapshot()
        bad = deepcopy(preset)
        bad['catalog_assets']['files'].pop('experiments/modal_idle_v1/F2_fixed_idle.msource')
        save(out/'invalid-preset.json',bad)
        with patch('vehicle_controller.ui.filedialog.askopenfilename',return_value=str(out/'invalid-preset.json')):
            window.restore()
        assert snapshot() == before
        assert '不匹配' in window.message.get()
        with patch('vehicle_controller.ui.filedialog.asksaveasfilename',return_value=str(out/'saved-preset.json')):
            window.save()
        saved = load(out/'saved-preset.json')
        recipe.validate(window.bridge,saved)
        assert saved['schema'].endswith('/8')
        assert saved['catalog_assets'] == preset['catalog_assets']
        for key in ('event_overrides','startup_response','event_policy','dna_bank'):
            assert saved[key] == preset[key]
        pump()
        screenshot('controls.png')
        # Invoke the actual Tk button, not a separately supplied replay.
        window.demo_button.invoke()
        assert window.running() and window.replaying
        first_state, actual = complete()
        reference = take.read(args.evidence/'idle_layer/lifecycle.vsltake.json',window.bridge)
        for key in ('initial','events','frames','source_events','event_overrides','startup_response','event_policy','dna_bank'):
            assert actual[key] == reference[key], key
        assert actual['schema'].endswith('/9')
        window.save_take()
        files = list((out/'takes').glob('*.vsltake.json'))
        assert len(files) == 1
        path = files[0]
        assert take.read(path,window.bridge) == actual
        screenshot('complete-flow.png')
        with patch('vehicle_controller.ui.filedialog.askopenfilename',return_value=str(path)):
            window.open_take()
        assert window.running()
        second_state, replay = complete()
        assert replay == actual
        screenshot('replayed.png')
        report.update(result='passed', actual_complete_flow_button=True, flows=2, frames_each=36*48000,
            saved_take_replay_exact=True, notices_state_exact=True, underflows_each=0,
            early_and_returned_idle_verified=True, idle_controls_enabled=True,
            invalid_manifest_preserves_UI=True, preset_roundtrip=True,
            catalog_assets_sha256=window.bridge.catalog_assets_sha256,
            bridge_sha256=window.bridge.sha256, ui_revision=13, source_ABI=window.bridge.abi(),
            terminal_controls_enabled=True, stopped_state_has_no_idle_label=True)
    except Exception as error:
        report.update(result='failed',error=repr(error))
        raise
    finally:
        window.stop()
        deadline = time.monotonic()+5
        while window.running() and time.monotonic() < deadline:
            pump()
        root.destroy()
        report['own_window_closed'] = True
        save(out/'report.json',report)


if __name__ == '__main__':
    main()
