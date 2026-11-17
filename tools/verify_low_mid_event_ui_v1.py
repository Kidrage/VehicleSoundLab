"""Load the E fullband candidate in an owned muted controller, save and replay."""
import argparse
import ctypes as C
from pathlib import Path
import shutil
import time
import tkinter as tk
from unittest.mock import patch

from PIL import ImageGrab

from research_archive_v1 import load, save, sha
from vehicle_controller import recipe, take
from vehicle_controller.ui import Window


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, args.output/'executed_verification.py')
    repo = Path(__file__).resolve().parents[1]
    expected = load(args.evidence/'report.json')
    root = tk.Tk()
    window = Window(root, repo, args.output/'takes')
    report = dict(result='running', goal_complete=False, timbre_accepted=False,
                  physical_identity_confirmed=False, audio_muted=True, own_window_closed=False,
                  persistent_service_restarted=False)

    def pump():
        root.update()
        time.sleep(.005)

    def screenshot(name):
        user = C.windll.user32
        user.GetAncestor.argtypes = [C.c_void_p, C.c_uint]
        user.GetAncestor.restype = C.c_void_p
        hwnd = user.GetAncestor(root.winfo_id(), 2)
        ImageGrab.grab(window=hwnd).save(args.output/name)

    try:
        pump()
        assert not window.running() and window.bridge.sha256 == expected['driver']['bridge_sha256']
        window.tabs.select(window.events_page)
        window.event_panel.import_profile(args.evidence/'event-profile.json')
        pump()
        info = window.event_panel.model_info.get()
        assert '全频参数候选' in info and '尚未确认' in info
        assert window.event_panel.buttons[3].instate(['!disabled'])
        screenshot('fullband-import.png')
        preset = args.evidence/'controller-preset.json'
        with patch('vehicle_controller.ui.filedialog.askopenfilename', return_value=str(preset)):
            window.restore()
        assert window.message.get() == '参数已载入。', window.message.get()
        original = load(preset)
        assert window.event_overrides == original['event_overrides']
        saved_preset = args.output/'UI-saved.preset.json'
        with patch('vehicle_controller.ui.filedialog.asksaveasfilename', return_value=str(saved_preset)):
            window.save()
        saved = load(saved_preset)
        recipe.validate(window.bridge, saved)
        for key in ('event_overrides', 'event_policy', 'startup_response', 'dna_bank', 'source_effective_sha256'):
            assert saved[key] == original[key], key
        for key in original['control']:
            if key != 'input':
                assert saved['control'][key] == original['control'][key], key
        report['import'] = dict(fullband_visible=True, unconfirmed_identity_visible=True,
                                parameter_roundtrip_exact=True, no_autoplay=True)
        window.muted.set(1)
        report['cases'] = []
        for variant in ('off', 'on'):
            value = take.read(args.evidence/f'drive-{variant}.take.json', window.bridge)
            window.start(value)
            host = window.host
            deadline = time.monotonic()+15
            seen = []
            while window.running() and time.monotonic() < deadline:
                pump()
                state = host.snapshot()
                if state.get('error'):
                    raise AssertionError(state)
                if state.get('active'):
                    seen.append(state['event_active'])
            assert not window.running(), variant
            final = host.snapshot()
            assert final['frame'] == value['frames'] and final['underflows'] == 0, final
            assert seen and max(seen) <= 4
            for key, target in expected['driver']['final_state'].items():
                assert final[key] == target, (variant, key, final[key], target)
            actual = host.take_snapshot()
            assert actual['source_events'] == value['source_events']
            assert actual['event_overrides'] == value['event_overrides']
            window.save_take()
            path = next(p for p in (args.output/'takes').glob('*.vsltake.json')
                        if p.name not in {r['saved_take'] for r in report['cases']})
            written = take.read(path, window.bridge)
            assert written['source_events'] == value['source_events']
            report['cases'].append(dict(variant=variant, frames=final['frame'], underflows=0,
                notices_exact=True, final_state_exact=True, max_sampled_active_voices=max(seen),
                saved_take=path.name, saved_take_sha256=sha(path), final_state=final))
            print(dict(variant=variant, frames=final['frame'], underflows=0), flush=True)
        screenshot('fullband-preset.png')
        binding = load(args.evidence.parent/'before/runtime.json')
        assert len(binding) == 459 and all(sha(repo/name) == digest for name, digest in binding.items())
        report.update(result='passed', runtime_voice_files_unchanged=459,
                      bridge_sha256=window.bridge.sha256)
    except Exception as error:
        report.update(result='failed', error=repr(error))
        raise
    finally:
        window.stop()
        deadline = time.monotonic()+5
        while window.running() and time.monotonic() < deadline:
            pump()
        root.destroy()
        report['own_window_closed'] = True
        save(args.output/'report.json', report)


if __name__ == '__main__':
    main()
