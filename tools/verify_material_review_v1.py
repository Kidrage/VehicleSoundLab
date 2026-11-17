"""Apply the human E-reference rejection and verify a source-only clean flow."""
import argparse
from copy import deepcopy
import ctypes as C
import hashlib
from pathlib import Path
import shutil
import tkinter as tk
from unittest.mock import patch

import numpy as np
from PIL import ImageGrab
import soundfile as sf

from event_authoring.material_reviews import rejection, ensure_live_reference, without_rejected
from event_designer.workspace import EventWorkspace
from vehicle_controller import recipe, take
from vehicle_controller.native import Bridge, Engine
from vehicle_controller.ui import Window
from vehicle_scenarios.capture import capture, replay
from vehicle_scenarios.review import build as build_review
from research_archive_v1 import load, save, sha


def must_refuse(call):
    try:
        call()
    except ValueError as error:
        assert '回火参考' in str(error), error
        return str(error)
    raise AssertionError('Rejected afterfire reference was accepted for new live use')


def ui_check(repo, out, short_path, old_path, clean_path):
    root = tk.Tk()
    window = Window(root, repo, out/'takes')
    screenshots = []
    def pump():
        root.update_idletasks()
        root.update()
    def shot(name):
        pump()
        user = C.windll.user32
        user.GetAncestor.argtypes = [C.c_void_p, C.c_uint]
        user.GetAncestor.restype = C.c_void_p
        ImageGrab.grab(window=user.GetAncestor(root.winfo_id(), 2)).save(out/name)
        screenshots.append(name)
    try:
        window.muted.set(1)
        pump()
        original = deepcopy(window.event_overrides)
        window.event_panel.import_profile(str(short_path))
        assert window.event_overrides == original and '回火参考' in window.message.get()
        before = deepcopy(dict(control=window.control, profiles=window.event_overrides,
                               response=window.startup_response, policy=window.event_policy, dna=window.dna_bank))
        with patch('vehicle_controller.ui.filedialog.askopenfilename', return_value=str(old_path)):
            window.restore()
        assert '回火参考' in window.message.get()
        assert before == dict(control=window.control, profiles=window.event_overrides,
                              response=window.startup_response, policy=window.event_policy, dna=window.dna_bank)
        # The historical document can still be inspected, but cannot start a new live session.
        window.event_overrides = deepcopy(load(old_path)['event_overrides'])
        window.event_panel.refresh()
        assert not window.event_panel.available_mask() & (1 << 3)
        assert window.event_panel.buttons[3].instate(['disabled'])
        window.event_panel.describe(3)
        window.tabs.select(window.events_page)
        shot('rejected-reference.png')
        old_control = deepcopy(window.control)
        window.start()
        assert window.host is None and window.control == old_control and '回火参考' in window.message.get()
        window.event_panel.remove_rejected.invoke()
        assert 'afterfire' not in window.event_overrides
        assert {'crank', 'catch'} <= set(window.event_overrides)
        assert window.vars['event_level_3'].get() == 0
        assert window.event_panel.remove_rejected.instate(['disabled'])
        with patch('vehicle_controller.ui.filedialog.askopenfilename', return_value=str(clean_path)):
            window.restore()
        assert window.event_overrides == load(clean_path)['event_overrides']
        assert window.message.get() == '参数已载入。'
        shot('clean-reference.png')
        return dict(real_Tk=True, no_audio_started=window.host is None,
            import_refused_without_mutation=True, old_preset_refused_without_mutation=True,
            live_start_refused=True, cleanup_preserves_startup=True, corrected_preset_loads=True,
            screenshots=screenshots, own_window_closed=True)
    finally:
        window.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output
    out.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    root = Path('E:/VehicleSoundLab/references/analysis')
    short_path = root/'low_mid_event_scan_v1/C1/review/event-profile.json'
    old_path = root/'catalog_asset_identity_v1/lifecycle1/controller-preset.json'
    old_take_path = root/'catalog_asset_identity_v1/lifecycle1/idle_layer/lifecycle.vsltake.json'
    old_audio = root/'catalog_asset_identity_v1/lifecycle1/review/idle_layer.wav'
    original_hashes = {str(p): sha(p) for p in [short_path, old_path, old_take_path, old_audio]}
    for p in [Path(__file__), repo/'research/material_review_decisions.json',
        *sorted((repo/'tools/vehicle_controller').glob('*.py')),
        repo/'tools/event_authoring/material_reviews.py', repo/'tools/event_designer/workspace.py',
        repo/'tools/event_designer/package.py', repo/'tools/sound_designer/web/events.js']:
        dest = out/'exact_sources'/p.relative_to(repo)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
    bridge = Bridge(repo)
    old = load(old_path)
    short = load(short_path)
    assert rejection(short) and rejection(old['event_overrides']['afterfire'])
    assert not rejection(old['event_overrides']['crank']) and not rejection(old['event_overrides']['catch'])
    near = deepcopy(short)
    near['parameters']['level'] *= .9
    near['provenance']['last_frame'] = short['provenance']['first_frame']
    near['provenance']['first_frame'] -= 4800
    assert not rejection(near), 'Adjacent non-overlap must not be rejected by this specific decision'
    stripped = deepcopy(short)
    stripped.pop('provenance')
    assert rejection(stripped), 'Renaming or dropping provenance does not rehabilitate exact rejected parameters'
    must_refuse(lambda: ensure_live_reference({'afterfire': short}))
    must_refuse(lambda: recipe.validate(bridge, old))
    must_refuse(lambda: recipe.create(bridge, old['catalog'], old['control'], old['mode'], old['event_overrides'],
        old['startup_response'], old['event_policy'], old['dna_bank']))
    must_refuse(lambda: take.create(bridge, old['catalog'], old['control'], old['event_overrides'],
        old['startup_response'], old['event_policy'], old['dna_bank']))
    # Existing immutable takes still validate and synthesize their original experiment.
    old_take = take.read(old_take_path, bridge)
    assert 'afterfire' in old_take['event_overrides']
    clean = without_rejected(old['event_overrides'])
    control = deepcopy(old['control'])
    control['events']['levels'][3] = 0.
    preset = recipe.create(bridge, old['catalog'], control, old['mode'], clean,
                           old['startup_response'], old['event_policy'], old['dna_bank'])
    clean_path = out/'controller-preset.json'
    save(clean_path, preset)
    assert recipe.validate(bridge, load(clean_path)) == clean
    value = take.create(bridge, old_take['catalog']['id'], old_take['initial'], clean,
        old_take['startup_response'], old_take['event_policy'], old_take['dna_bank'])
    value['initial']['events']['levels'][3] = 0.
    for event in old_take['events']:
        adopted = deepcopy(event['control'])
        adopted['events']['levels'][3] = 0.
        take.append(value, event['frame'], adopted)
    value['frames'] = old_take['frames']
    folder = out/'clean-flow'
    folder.mkdir()
    result, telemetry, transitions = capture(bridge, value, folder)
    assert all(n['type'] != 3 for n in value['source_events'])
    assert {n['type'] for n in value['source_events']} == {1, 2}
    replayed = replay(bridge, value)
    assert replayed['pcm_sha256'] == result['pcm_sha256']
    assert replayed['source_events'] == value['source_events']
    assert replayed['final_state'] == result['final_state']
    print('clean36s generation and variable-block replay exact; no afterfire source', flush=True)
    # Compare EVERY legacy C piece against clean native continuous stems.
    legacy_hash = hashlib.sha256()
    count = 0
    with Engine(bridge, old_take['catalog']['id'], old_take['event_overrides'],
        old_take['startup_response'], old_take['event_policy'], old_take['dna_bank']) as engine, \
            sf.SoundFile(folder/'native.wav') as cleaned, sf.SoundFile(old_audio) as historical:
        engine.set(old_take['initial'])
        index = 0
        while engine.frame < old_take['frames']:
            while index < len(old_take['events']) and old_take['events'][index]['frame'] == engine.frame:
                engine.set(old_take['events'][index]['control'])
                index += 1
            frames = min((137, 511, 240, 1024, 17)[count % 5], old_take['frames']-engine.frame,
                old_take['events'][index]['frame']-engine.frame if index < len(old_take['events']) else old_take['frames'])
            pcm = engine.process(frames)
            legacy_hash.update(pcm)
            old_stems = np.ctypeslib.as_array(engine.stems)[:frames*23].reshape(frames, 23)
            clean_stems = cleaned.read(frames, dtype='float32', always_2d=True)
            assert np.array_equal(old_stems[:, :19], clean_stems[:, :19])
            assert np.array_equal(np.frombuffer(pcm, dtype='<f4').reshape(-1, 2),
                                  historical.read(frames, dtype='float32', always_2d=True))
            count += 1
    print('all19 continuous channels unchanged; historical experiment PCM exact', flush=True)
    # Workbench history remains inspectable and explicitly carries the user decision.
    authoring = EventWorkspace(repo, out/'event-projects')
    project = authoring.create(dict(package=short))
    assert project['material_review']['decision'] == 'reject_reference'
    from event_designer.package import export
    from event_authoring.native import Renderer, controls
    author_wave, author_details = Renderer(repo).render(short['parameters'], 'afterfire', controls({}))
    export_folder = out/'historical-export'
    export_folder.mkdir()
    export(export_folder, short, controls({}), author_details)
    exported = load(export_folder/'parameters.json')
    assert exported['material_review']['decision'] == 'reject_reference'
    assert 'Historical experiment' in (export_folder/'profile.h').read_text(encoding='utf-8')
    ui_folder = out/'ui'
    ui_folder.mkdir()
    ui = ui_check(repo, ui_folder, short_path, old_path, clean_path)
    for p, digest in original_hashes.items():
        assert sha(Path(p)) == digest
    runtime = load(root/'A_exterior_startup_v1/selection1/runtime.json')
    assert len(runtime) == 459 and all(sha(repo/name) == digest for name, digest in runtime.items())
    scenario = load(root/'catalog_asset_identity_v1/lifecycle1/idle_layer/scenario.json')
    for stage in scenario['stages']:
        if stage['name'] == 'LIFT':
            stage['note'] = 'Hold gear on lift. Rejected E reference removed; afterfire awaits a suitable source.'
    save(folder/'scenario.json', scenario)
    verification = dict(result, checks=[dict(name='exact_replay_stems_and_review_decision', passed=True)],
        bridge_sha256=bridge.sha256,
        review_introduction='已移除被否决的E回火参考。保留车外启动、接火、怠速和行驶；当前收油不播放该短声。转速来自C驾驶器，非素材实测。',
        review_listening_hint='听完整流程或独奏各层。独立事件目前只在启动／接火阶段发声。',
        event_profile_description='A crank/catch retained. Human-rejected E afterfire reference removed; new afterfire material pending.')
    save(folder/'verification.json', verification)
    review = build_review(folder, out/'review')
    shutil.copy2(clean_path, out/'review/controller-preset.json')
    html_path = out/'review/index.html'
    html = html_path.read_text(encoding='utf-8')
    html = html.replace('</main>', '<p><a href="controller-preset.json" download>下载已移除该回火参考的控制配方</a></p></main>')
    html_path.write_text(html, encoding='utf-8')
    save(out/'report.json', dict(result='passed', review_decision=load(repo/'research/material_review_decisions.json'),
        corrected_preset=str(clean_path), flow=result, replay=replayed, continuous_native_channels_exact=19,
        every_legacy_piece_checked=count, legacy_PCM_sha256=legacy_hash.hexdigest(),
        historical_files_unchanged=original_hashes, historical_take_read_and_PCM_exact=True,
        old_afterfire_refused_for_new_live_preset_and_take=True, workbench_review_display_data=True,
        historical_exports_marked=True, UI=ui, review=review, runtime_voice_files_unchanged=459,
        persistent_service_restarted=False, goal_complete=False, timbre_accepted=False))
    print('material review, clean flow, historical replay, workbench exports and owned Tk passed', flush=True)


if __name__ == '__main__':
    main()
