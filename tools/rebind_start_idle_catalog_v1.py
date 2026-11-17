"""Recreate the frozen lifecycle with current identities, then compare actual C PCM."""
import argparse
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from research_archive_v1 import load, save, sha
from vehicle_controller import recipe, take
from vehicle_controller.native import Bridge, Engine
from vehicle_scenarios.start_idle import start_idle_lifecycle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, out/'executed_verification.py')
    repo = Path(__file__).resolve().parents[1]
    data = Path('E:/VehicleSoundLab')
    base = data/'baselines/start_idle_lifecycle_v1/delivery1'
    previous = base/'evidence/C3'
    report = dict(result='running', goal_complete=False, timbre_accepted=False)
    try:
        assert sha(base/'manifest.json') == '677f361054150d15a6a6972410a23ceefd34379994f3305242a5ba703694ed9b'
        manifest = load(base/'manifest.json')
        assert all(sha(base/row['path']) == row['sha256'] for row in manifest['files'])
        runtime = load(data/'baselines/A_exterior_startup_v1/delivery1/evidence/selection1/runtime.json')
        assert len(runtime) == 459 and all(sha(repo/name) == digest for name,digest in runtime.items())
        binding = load(repo/'research/start_idle_lifecycle_v1_verification.json')
        assert all(sha(repo/name) == digest for name,digest in binding['additional_legacy_idle_inputs'].items())
        expected = load(previous/'report.json')
        bridge = Bridge(repo)
        assert bridge.sha256 == expected['bridge_sha256'] and bridge.channels() == 23
        results = {}
        for name in ('main_only', 'idle_layer'):
            old = load(previous/name/'lifecycle.vsltake.json')
            assert old['schema'] == 'vsl.source-controller-take/8'
            assert old['bridge_sha256'] == bridge.sha256
            assert old['voices_sha256'] == bridge.voices_sha256
            value, scenario = start_idle_lifecycle(bridge, old['catalog']['id'], old['initial'],
                old['event_overrides'], old['startup_response'], old['event_policy'], old['dna_bank'])
            for key in ('catalog','initial','events','frames','event_overrides','startup_response','event_policy','dna_bank'):
                assert value[key] == old[key], key
            folder = out/name
            folder.mkdir()
            notices = []
            calls = index = block = 0
            pattern = (1,1024,137,511,17,240,731)
            with sf.SoundFile(previous/name/'native.wav') as native, sf.SoundFile(previous/name/'mix.wav') as monitor:
                assert native.channels == 23 and monitor.channels == 2
                assert len(native) == len(monitor) == value['frames']
                with Engine(bridge, value['catalog']['id'], value['event_overrides'], value['startup_response'],
                            value['event_policy'], value['dna_bank']) as engine:
                    engine.set(value['initial'])
                    original = engine.process
                    def compare_piece(frames, solo=-1):
                        nonlocal calls
                        pcm = original(frames, solo)
                        actual = np.ctypeslib.as_array(engine.stems)[:frames*23].reshape(frames,23)
                        assert np.array_equal(actual, native.read(frames, dtype='float32', always_2d=True))
                        calls += 1
                        return pcm
                    engine.process = compare_piece
                    while engine.frame < value['frames']:
                        pcm,index = take.replay_block(engine, value, index, pattern[block%len(pattern)])
                        actual = np.frombuffer(pcm,dtype='<f4').reshape(-1,2)
                        assert np.array_equal(actual, monitor.read(len(actual), dtype='float32', always_2d=True))
                        notices.extend(engine.last_events)
                        block += 1
                    state = engine.state()
                assert native.tell() == monitor.tell() == value['frames']
            assert notices == old['source_events']
            assert state == expected['measurements'][name]['final_state']
            value['source_events'] = notices
            path = folder/'lifecycle.vsltake.json'
            take.save(path, value)
            assert take.read(path, bridge) == value
            save(folder/'scenario.json', scenario)
            results[name] = dict(native_23channels_exact=True, monitor_exact=True, notices_state_exact=True,
                actual_native_process_calls=calls, host_blocks=block, frames=state['frame'], final_state=state,
                reference_native_sha256=sha(previous/name/'native.wav'), current_take_sha256=sha(path))
            print(name, 'new identity, every native piece exact', flush=True)
        old_preset = load(previous/'controller-preset.json')
        preset = recipe.create(bridge, old_preset['catalog'], old_preset['control'], old_preset['mode'],
            old_preset['event_overrides'], old_preset['startup_response'], old_preset['event_policy'], old_preset['dna_bank'])
        recipe.validate(bridge, preset)
        save(out/'controller-preset.json', preset)
        review = out/'review'
        shutil.copytree(previous/'review', review)
        shutil.copy2(out/'controller-preset.json', review/'controller-preset.json')
        shutil.copy2(out/'idle_layer/lifecycle.vsltake.json', review/'full.take.json')
        html = (review/'index.html').read_text(encoding='utf-8')
        marker = '<div class="tracks">'
        assert html.count(marker) == 1
        html = html.replace(marker, '<p>下载参数适用于独立控制窗口V13：完整流程按钮运行同一36秒场景。声音与上次C3逐样本一致，本页更新了参数和行程的完整资产校验；旧V12文件继续由冻结版本回放。</p>'+marker)
        (review/'index.html').write_text(html, encoding='utf-8')
        tracks = load(review/'tracks.json')
        assert len(tracks) == 8 and all(sha(review/row['file']) == row['sha256'] for row in tracks)
        report.update(result='passed', baseline=str(base), baseline_manifest_sha256=sha(base/'manifest.json'),
            baseline_all_133_files_exact=True, runtime_459_and_89voices_exact=True, legacy_F2_inputs_exact=True,
            bridge_sha256=bridge.sha256, source_ABI=bridge.abi(), ui_revision=13, cases=results,
            catalog_assets_sha256=bridge.catalog_assets_sha256, catalog_file_count=92,
            preset_schema=preset['schema'], take_schema=value['schema'], review=str(review),
            review_audio_reused_only_after_actual_C_comparison=True, physical_afterfire_confirmed=False,
            source_only=True, new_download=False, spatial_added=False, ADI_optimization=False)
    except Exception as error:
        report.update(result='failed', error=repr(error))
        raise
    finally:
        save(out/'report.json', report)


if __name__ == '__main__':
    main()
