"""Compose actual F2 idle with exterior startup in the existing source-only C system."""
import argparse
import csv
from copy import deepcopy
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from event_review import page
from research_archive_v1 import load, save, sha
from vehicle_controller import recipe, take
from vehicle_controller.native import Bridge
from vehicle_scenarios.capture import capture, replay
from vehicle_scenarios.start_idle import start_idle_lifecycle


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--reuse-captures', type=Path)
    args = p.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, out/'executed_build.py')
    repo = Path(__file__).resolve().parents[1]
    shutil.copy2(repo/'tools/vehicle_scenarios/start_idle.py',out/'executed_scenario.py')
    shutil.copy2(repo/'research/start_idle_lifecycle_v1_plan.json',out/'plan.json')
    root = Path('E:/VehicleSoundLab/references/analysis')
    source = root/'A_exterior_startup_v1'
    milestone = load(repo/'research/A_exterior_startup_v1_verification.json')
    verify = load(source/'verification5/report.json')
    bridge = Bridge(repo)
    assert bridge.sha256 == milestone['bridge_sha256'] and bridge.channels() == 23
    selection = next(row['id'] for row in bridge.catalog if row['key'] == 'v10-moving-fine-idle')
    initial, capabilities = bridge.initial(selection)
    assert capabilities & 32 and capabilities & 64
    initial.update(gain=.25, legacy_event_gain=0., startup_gain=0., catch_gain=0.,
                   idle_motion=.5, idle_detail=1., backfire=1)
    initial['events'].update(enabled=1, gain=.5, pitch=1., decay=1., texture=1.)
    initial['events']['levels'] = [0., 1., .25, 1., 0., 0., 0.]
    profiles = {kind: load(verify['profiles'][kind]['document']) for kind in ('crank', 'catch')}
    profiles['afterfire'] = load(root/'event_full_envelope_v1/C4/event-profile.json')
    response = deepcopy(bridge.startup_defaults)
    response['crank_seconds'] = .588
    report = dict(result='running', goal_complete=False, timbre_accepted=False,
        physical_afterfire_confirmed=False, prior_demo_idle_claim_corrected=True,
        previous_demo=dict(catalog='v10-moving35', actual_F2_idle_profile=False),
        current_catalog='v10-moving-fine-idle', source_only=True)
    measured, telemetry, values, native = {}, {}, {}, {}
    try:
        for name, amount in [('main_only', 0.), ('idle_layer', 1.)]:
            control = deepcopy(initial)
            control['idle_mix'] = amount
            value, scenario = start_idle_lifecycle(bridge, selection, control, profiles, response)
            folder = out/name
            if args.reuse_captures:
                previous = args.reuse_captures/name
                checked = load(previous/'verification.json')
                assert checked['result'] == 'passed'
                old = take.read(previous/'lifecycle.vsltake.json', bridge)
                for key in ('catalog','initial','events','frames','event_overrides','startup_response','event_policy','dna_bank'):
                    assert old.get(key) == value.get(key), key
                shutil.copytree(previous, folder)
                value = old
                result, check = checked['measured'], checked['replay']
                with (folder/'telemetry.csv').open(encoding='utf-8', newline='') as stream:
                    rows = [{k:v if k.endswith('_name') else float(v) for k,v in row.items()}
                            for row in csv.DictReader(stream)]
                save(folder/'reused-capture.json', dict(path=str(previous),
                    verification_sha256=sha(previous/'verification.json'),
                    native_sha256=sha(previous/'native.wav'), reason='Capture/replay passed; only the later exact-zero test assumption failed.'))
            else:
                folder.mkdir()
                save(folder/'scenario.json', scenario)
                result, rows, transitions = capture(bridge, value, folder)
                check = replay(bridge, value)
            assert check['pcm_sha256'] == result['pcm_sha256']
            assert check['source_events'] == value['source_events'] and check['final_state'] == result['final_state']
            assert result['native_reconstruction_error'] < 2e-6
            assert result['final_state']['lifecycle'] == 0
            assert all(result['final_state'][k] == 0 for k in ('event_rejected', 'event_overflow', 'event_log_lost'))
            save(folder/'verification.json', dict(result='passed', measured=result, replay=check))
            native[name], rate = sf.read(folder/'native.wav', dtype='float32', always_2d=True)
            assert rate == 48000 and native[name].shape == (36*48000, 23)
            measured[name], telemetry[name], values[name] = result, rows, value
            print(name, 'actual C capture and replay passed', flush=True)
        assert values['main_only']['source_events'] == values['idle_layer']['source_events']
        assert measured['main_only']['final_state'] == measured['idle_layer']['final_state']
        assert np.array_equal(native['main_only'][:,19:], native['idle_layer'][:,19:])
        drive_fields = ('frame', 'rpm', 'speed_mps', 'acceleration_mps2', 'load', 'gear',
                        'lifecycle', 'operating', 'shifts', 'overruns')
        assert all(all(a[k] == b[k] for k in drive_fields)
                   for a,b in zip(telemetry['main_only'], telemetry['idle_layer']))
        # Catalog initialization starts at amount1. A frame0 amount0 request
        # follows the existing18ms smoother; its infinitesimal tail is not exact0.
        baseline_weight = max(row['idle_weight'] for row in telemetry['main_only'])
        assert baseline_weight < 1e-15
        rows = telemetry['idle_layer']
        windows = {}
        for name, lo, hi in [('after_start', 3., 5.5), ('accelerating', 9., 17.), ('parked', 31., 33.5)]:
            segment = [row for row in rows if lo <= row['seconds'] < hi]
            windows[name] = dict(weight_min=min(r['idle_weight'] for r in segment),
                weight_max=max(r['idle_weight'] for r in segment),
                rpm_min=min(r['rpm'] for r in segment), rpm_max=max(r['rpm'] for r in segment),
                added_rms_mean=float(np.mean([r['rms_added'] for r in segment])))
        assert windows['after_start']['weight_min'] > .99 and windows['parked']['weight_min'] > .99
        assert windows['accelerating']['weight_max'] < .01
        assert all(row['idle_weight'] > .99 and row['operating'] == 0
                   for row in rows if 29 <= row['seconds'] < 33.5)
        assert windows['after_start']['added_rms_mean'] > 0 and windows['parked']['added_rms_mean'] > 0
        assert rows[-1]['idle_weight'] < 1e-5
        offsets = np.cumsum([0]+[r['channels'] for r in bridge.stems])
        added_index = next(i for i,r in enumerate(bridge.stems) if r['name'] == 'added')
        a,b = offsets[added_index:added_index+2]
        baseline_added_peak = float(np.max(abs(native['main_only'][:,a:b])))
        assert baseline_added_peak < 1e-12 and np.any(native['idle_layer'][:,a:b])
        full = values['idle_layer']
        preset = recipe.create(bridge, selection, full['initial'], '踏板驾驶', profiles, response)
        recipe.validate(bridge, preset)
        save(out/'controller-preset.json', preset)
        review = out/'review'
        review.mkdir()
        tracks = []
        def add(label, x, file, description, scale=1.):
            x = np.asarray(x)
            sf.write(review/file, x*scale, 48000, subtype='FLOAT')
            tracks.append(dict(label=label, file=file, description=description, gain=scale,
                frames=len(x), channels=1 if x.ndim == 1 else x.shape[1], sha256=sha(review/file)))
        for name,label in [('main_only','仅行驶声线延伸到怠速'), ('idle_layer','真正接入F2怠速层')]:
            mix,_ = sf.read(out/name/'mix.wav', always_2d=True)
            add(label+' · 完整36秒', mix, name+'.wav', '相同启动、踏板、挡位和独立事件；只改变怠速混合量。')
            add(label+' · 启动后6秒', mix[:6*48000], name+'-start.wav', '0.35秒启动，其后驻车，6秒才挂挡给油。')
            add(label+' · 停车后怠速', mix[30*48000:34*48000], name+'-parked.wav', '完整流程30–34秒原位切出，不重新生成。')
        add('F2怠速 · 原生独立干声分轨', native['idle_layer'][:,a:b], 'idle-stem.wav', '现有added分轨，仅含F2模态与程序细谱；未新增混响。')
        add('独立事件 · 两版完全相同', native['idle_layer'][:,19:].sum(axis=1)*2**-.5,
            'events.wav', '启动、接火及E收油候选的电气mono汇总；四个原始事件槽保留在native导出。')
        for file,src in [('controller-preset.json',out/'controller-preset.json'),
                         ('full.take.json',out/'idle_layer/lifecycle.vsltake.json')]:
            shutil.copy2(src, review/file)
        save(review/'tracks.json', tracks)
        seconds = np.array([row['seconds'] for row in rows])
        fig, axes = plt.subplots(3, 1, figsize=(11, 7), sharex=True, layout='constrained')
        for axis, key, label in zip(axes, ('rpm','idle_weight','rms_added'), ('Virtual RPM','Idle replacement weight','F2 dry-stem RMS')):
            axis.plot(seconds, [row[key] for row in rows], linewidth=1)
            axis.set_ylabel(label)
            axis.grid(alpha=.25)
            for when in (6,7,19,21,30,34):axis.axvline(when, color='.6', linewidth=.5)
        axes[-1].set_xlabel('Seconds from one source-engine sample clock')
        fig.savefig(review/'curves.png', dpi=130)
        plt.close(fig)
        prose = [
            '此页修正上一版启动对照的接线说明：上一版使用仅行驶预设，实际上没有载入F2怠速。这里两版都使用同一含F2的目录配置，只把怠速混合从0改为100%。',
            '先比较两条“启动后6秒”，再比较“停车后怠速”。完整流程在0.35秒启动、6秒挂挡、7秒深踩、19秒收油、21秒制动、30秒保挡制动怠速、34秒熄火；RPM与状态由C驾驶器生成。',
            'F2层由模态OSC、统计幅度变化及程序噪声的细谱滤波持续生成，不播放原录音；运行中怠速自动淡入，给油后自动淡出。旧算法和参数没有改动，这次判断真实整车接线和过渡。',
            '固定主增益0.25，事件增益0.5、接火25%；没有房间处理、限幅或逐条归一化。A车外/F2怠速/E短声仍是多来源工程配方，收油短声尚未确认为物理回火，声音质量需听评。',
            '停止独立控制窗口后载入controller-preset.json，可调怠速声线、主声线起伏、细谱纹理；full.take.json用于完整36秒重放。独立窗口和工作台使用同一C声源系统。']
        html = page('启动 → 真正的怠速层 → 驾驶', prose, tracks,
            [('controller-preset.json','controller-preset.json'), ('full.take.json','full.take.json')])
        html = html.replace('原素材与新旧C的高频能量起伏对照','实际C转速、怠速权重与F2干声分轨电平')
        (review/'index.html').write_text(html, encoding='utf-8')
        bindings = load(source/'selection1/runtime.json')
        assert len(bindings) == 459 and all(sha(repo/name) == digest for name,digest in bindings.items())
        report.update(result='passed', bridge_sha256=bridge.sha256, source_ABI=bridge.abi(),
            measurements=measured, idle_windows=windows, control_trajectory_exact=True,
            event_4channels_and_notices_exact=True, idle_added_bus_proven=True,
            baseline_smoothed_weight_max=baseline_weight, baseline_added_peak_FS=baseline_added_peak,
            captures_reused=args.reuse_captures is not None,
            runtime_voice_files_unchanged=459, review=str(review),
            sources={'scenario':sha(repo/'tools/vehicle_scenarios/start_idle.py'),
                     'builder':sha(__file__), 'plan':sha(repo/'research/start_idle_lifecycle_v1_plan.json')})
    except Exception as error:
        report.update(result='failed', error=repr(error))
        raise
    finally:
        save(out/'report.json', report)


if __name__ == '__main__':
    main()
