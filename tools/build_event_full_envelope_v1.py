"""Compare immutable E100ms and full310ms profiles in one real C driver."""
import argparse
from copy import deepcopy
import hashlib
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from event_authoring.audio import read
from event_review import page
from research_archive_v1 import load, save, sha
from vehicle_controller import take, recipe
from vehicle_controller.native import Bridge
from vehicle_scenarios.capture import capture, replay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--captures-from', type=Path,
                        help='Reuse completed per-variant captures after an assembly-only failure')
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, out/'executed_build.py')
    repo = Path(__file__).resolve().parents[1]
    root = Path('E:/VehicleSoundLab/references/analysis/event_full_envelope_v1')
    previous = root.parent/'low_mid_event_scan_v1/C1'
    report = dict(result='running', goal_complete=False, timbre_accepted=False,
                  physical_identity_confirmed=False)
    try:
        checks = {name: load(root/name/'report.json') for name in ('verification1', 'audit1')}
        assert all(row['result'] == 'passed' for row in checks.values())
        web = load(root/'web1/verification.json')
        assert web['result'] == 'passed' and web['source_free_import_C_PCM_exact']
        documents = {
            'short': load(previous/'event-profile.json'),
            'original': load(root/'verification1/original/analysis/profile.json'),
            'on': load(root/'verification1/candidate/analysis/profile.json')}
        assert documents['on']['source_job'] == load(repo/'research/E_full_event_v1.job.json')
        assert documents['short']['parameters']['duration_seconds'] == .1
        assert documents['on']['parameters']['duration_seconds'] == .31
        imported = load(web['actual_parameters'])
        assert imported['document']['parameters'] == documents['on']['parameters']
        bridge = Bridge(repo)
        assert bridge.abi() == 11 and bridge.channels() == 23
        selection = next(r['id'] for r in bridge.catalog if r['key'] == 'v10-moving35')
        initial = bridge.initial(selection)[0]
        initial.update(mode=1, ignition=1, start_id=1, gear=0, automatic=0,
                       throttle=0., brake=.7, gain=.25, backfire=1)
        initial['events'].update(enabled=1, gain=.5, pitch=1., decay=1., texture=1., manual_sequence=0)
        initial['events']['levels'] = [0., 0., 0., 1., 0., 0., 0.]
        startup = deepcopy(bridge.startup_defaults)
        captures = {}
        for name in ('off', 'short', 'original', 'on'):
            document = documents['on' if name == 'off' else name]
            overrides = {'afterfire': document}
            control = deepcopy(initial)
            if name == 'off':
                control['events']['levels'][3] = 0.
            value = take.create(bridge, selection, control, overrides, startup)
            value['frames'] = 8*48000
            for seconds, changes in ((1.7, dict(throttle=.65)), (3.7, dict(throttle=0.)),
                                     (5., dict(throttle=.45)), (6.5, dict(throttle=0.))):
                control.update(changes)
                take.append(value, round(seconds*48000), control)
            folder = out/name
            if args.captures_from:
                old = args.captures_from/name
                checkpoint = load(old/'report.json')
                assert checkpoint['result'] == 'passed'
                restored = take.read(old/'lifecycle.vsltake.json', bridge)
                without_notices = deepcopy(restored)
                without_notices['source_events'] = []
                for key in ('created', 'stream_id'):
                    without_notices[key] = value[key]
                assert without_notices == value
                shutil.copytree(old, folder)
                value = restored
                measured = checkpoint['measurement']
                check = checkpoint['variable_block_monitor_replay']
            else:
                folder.mkdir()
                measured, _, _ = capture(bridge, value, folder)
                check = replay(bridge, value)
            assert check['pcm_sha256'] == measured['pcm_sha256']
            assert check['source_events'] == value['source_events']
            assert check['final_state'] == measured['final_state']
            state = measured['final_state']
            assert all(state[k] == 0 for k in ('event_rejected', 'event_overflow', 'event_log_lost'))
            assert state['event_peak'] <= 4 and state['event_active'] == state['event_queue'] == 0
            starts = [r for r in value['source_events'] if r['action'] == 1 and r['type'] == 3]
            assert len(starts) == 4 and all(r['frame'] == r['requested_frame'] for r in starts)
            native, _ = sf.read(folder/'native.wav', dtype='float32', always_2d=True)
            mix, _ = sf.read(folder/'mix.wav', dtype='float32', always_2d=True)
            assert native.shape == (384000, 23)
            assert hashlib.sha256(mix.astype('<f4').tobytes()).hexdigest() == measured['pcm_sha256']
            save(folder/'report.json', dict(result='passed', measurement=measured,
                variable_block_monitor_replay=check, starts=starts))
            captures[name] = dict(take=value, measurement=measured, native=native, mix=mix,
                                  starts=starts)
            print(name, 'actual C capture and monitor replay passed', flush=True)
        reference = captures['on']
        assert all(np.array_equal(row['native'][:, :19], reference['native'][:, :19]) for row in captures.values())
        assert captures['off']['take']['source_events'] == reference['take']['source_events']
        assert captures['off']['measurement']['final_state'] == reference['measurement']['final_state']
        assert not np.any(captures['off']['native'][:, 19:])
        # Longer sounds overlap. Start opportunities remain fixed; pool slots
        # are reusable resources and are allowed to differ with event duration.
        fields = ('frame', 'requested_frame', 'id', 'type')
        assert all([[r[k] for k in fields] for r in row['starts']] ==
                   [[r[k] for k in fields] for r in reference['starts']] for row in captures.values())
        event = reference['native'][:, 19:].sum(axis=1)*2**-.5
        event_mix = np.column_stack((event, event))
        error = float(np.max(abs(reference['mix'].astype(float)-captures['off']['mix']-event_mix)))
        assert error < 2e-7
        sf.write(out/'drive-events.wav', event_mix, 48000, subtype='FLOAT')
        for name in ('off', 'on'):
            shutil.copy2(out/name/'mix.wav', out/('drive-'+name+'.wav'))
            shutil.copy2(out/name/'native.wav', out/('native-'+name+'.wav'))
            shutil.copy2(out/name/'lifecycle.vsltake.json', out/('drive-'+name+'.take.json'))
        take.save(out/'controller-preset.json', recipe.create(bridge, selection, initial,
                  '踏板驾驶', {'afterfire': documents['on']}, startup))
        save(out/'event-profile.json', documents['on'])
        review = out/'review'
        review.mkdir()
        tracks = []
        def add(label, source, name, description, scale=.25):
            wave, rate = sf.read(source, always_2d=True)
            sf.write(review/name, wave*scale, rate, subtype='FLOAT')
            tracks.append(dict(label=label, file=name, description=description, gain=scale,
                frames=len(wave), channels=wave.shape[1], sha256=sha(review/name)))
        add('E 原声上下文', previous/'original-context.wav', 'context.wav', '原13.34–15.84秒；声学变化约在第1秒。')
        add('E 原声 · 背景间完整310ms区间', root/'verification1/candidate/analysis/reference.wav', 'crop.wav', '14.19–14.50秒，包含持续发动机和环境；未分离物理声源。')
        add('旧100ms合成', previous/'C-27431.wav', 'short.wav', '原候选保持；这是检测窗，不能代表完整动作。')
        add('310ms · 原单段包络', root/'verification1/original/C-27431.wav', 'original.wav', '只延长首尾，同一有限响应校准。')
        add('310ms · 新分频包络', root/'verification1/candidate/C-27431.wav', 'candidate.wav', '只为可靠60–300Hz提取时间形状；中频时间形状有退步。')
        for name, label in [('off', '短声关闭'), ('short', '旧100ms'), ('original', '310ms原包络'), ('on', '310ms新包络')]:
            add('C补油收油 · '+label, out/name/'mix.wav', 'drive-'+name+'.wav',
                '同一8秒工程动作、主增益与事件电平；19持续通道完全相同。', scale=1.)
        add('C补油收油 · 只听新事件', out/'drive-events.wav', 'drive-events.wav',
            '独立事件声部分轨汇总，启动释放等其他事件电平为零。', scale=1.)
        for name in ('event-profile.json', 'controller-preset.json', 'drive-on.take.json'):
            shutil.copy2(out/name, review/name)
        audit = checks['audit1']
        fig, axes = plt.subplots(2, 1, figsize=(11, 6), layout='constrained')
        from event_authoring.temporal_fit import band_curves
        job = documents['on']['source_job']
        source, _, _ = read(job['source'], *job['seconds'])
        noise, _, _ = read(job['source'], *job['background_seconds'])
        t, power = band_curves(source)
        _, bp = band_curves(noise)
        target = np.maximum(power-bp.mean(axis=1)[:, None], 0)
        for index, ax in enumerate(axes):
            ax.plot(t, target[index]/max(target[index].mean(), 1e-30), label='Recorded positive excess')
            for name, label in [('original', 'Original local envelope'), ('candidate', 'New LF contour')]:
                wave, _ = sf.read(root/f'verification1/{name}/C-27431.wav')
                tt, pp = band_curves(wave[:len(source)])
                ax.plot(tt, pp[index]/max(pp[index].mean(), 1e-30), label=label)
            ax.set(xlabel='Seconds inside fixed310ms interval', ylabel='Mean-normalized power',
                   title=('60–300 Hz: reliable' if index == 0 else '300–1200 Hz: low contrast / new candidate regresses'))
            ax.grid(alpha=.2)
            ax.legend()
        fig.savefig(review/'curves.png', dpi=140)
        plt.close(fig)
        prose = [
            '这轮修正事件范围与提参能力：旧100ms检测窗未覆盖声学建立和衰减。新选区严格采用原前后背景之间的整个14.19–14.50秒，没有换更安静背景。它仍不是已确认的物理回火。',
            '先比较原声上下文、310ms原声，再听旧100ms／310ms原包络／新分频包络。新候选仅60–300Hz达到独立增量门槛；低频时间形状误差约0.76→0.12，但300–1200Hz约1.44→1.86，不能称整段音色已改善。其他频带保留局部包络，没有凭空补高频。',
            '随后比较四条8秒补油收油完整混音。19个持续通道与驾驶信号逐样本相同，四次事件起点相同；较长尾音会改变声部重叠与结束通知。这些是工程踏板动作，没有复刻原视频RPM和喷油轨迹。',
            '原声／单次C统一乘0.25；驾驶使用同一主增益0.25、事件增益0.5。没有房间处理、压缩、原音频循环或逐条响度补偿。新候选并不替换原认可DNA或正式事件库。停止独立窗口后可载入配方试听。']
        text = page('完整短声与四频段包络 · E候选', prose, tracks,
                    [(f, f) for f in ('event-profile.json', 'controller-preset.json', 'drive-on.take.json')])
        text = text.replace('原素材与新旧C的高频能量起伏对照', '可靠低频的改善与中频时间形状退步')
        (review/'index.html').write_text(text, encoding='utf-8')
        save(review/'tracks.json', tracks)
        baseline = load(root/'before/runtime.json')
        assert all(sha(repo/name) == digest for name, digest in baseline.items())
        report.update(result='passed', actual_editable_project=web['actual_editable_project'],
            driver=dict(bridge_sha256=bridge.sha256, source_ABI=11, frames=384000,
                continuous_19channels_exact=True, starts_across_duration_variants_exact=True,
                off_on_same_profile_notices_state_exact=True, starts=reference['starts'],
                final_state=reference['measurement']['final_state'], mix_error_FS=error),
            captures={name: row['measurement'] for name, row in captures.items()},
            runtime_voice_files_unchanged=len(baseline), physical_type='unclassified acoustic interval',
            captures_reused_from=str(args.captures_from) if args.captures_from else None,
            spectral_temporal_audit_sha256=sha(root/'audit1/report.json'), review=str(review))
    except Exception as error:
        report.update(result='failed', error=repr(error))
        raise
    finally:
        save(out/'report.json', report)
    print(dict(result='passed', review=str(review)), flush=True)


if __name__ == '__main__':
    main()
