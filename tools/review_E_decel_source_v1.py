"""Audition new C-generated slowing-context timbre against old cabin/source audio."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

p = argparse.ArgumentParser(description=__doc__)
for key in ('workspace', 'fit', 'audit', 'out', 'dna-probe'):
    p.add_argument('--'+key, type=Path, required=True)
p.add_argument('--stereo', type=Path)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
for key in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[key] = '2'
import json
import numpy as np
import soundfile as sf
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load, save, sha
from idle_texture_v1.profile import load as load_dna

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', inputs={}, clips=[], commands=[])


def consume(path):
    r['inputs'][str(path)] = sha(path)
    return path


def clip(scene, key, title, path, note):
    wave, rate = sf.read(consume(path), always_2d=True)
    assert rate == 48000 and wave.shape[1] == 2
    wave *= .5
    fade = np.sin(np.linspace(0, np.pi/2, 240))**2
    wave[:240] *= fade[:, None]
    wave[-240:] *= fade[::-1, None]
    assert abs(wave).max() < .95
    dest = a.out/(scene['key']+'_'+key+'.wav')
    sf.write(dest, wave, 48000, subtype='PCM_24')
    actual, rate = sf.read(dest, always_2d=True)
    assert rate == 48000 and abs(actual-wave).max() <= 2**-23
    url = 'http://127.0.0.1:8789/'+dest.relative_to(a.workspace).as_posix()
    with urllib.request.urlopen(url, timeout=20) as response:
        assert response.read() == dest.read_bytes()
    row = dict(key=key, title=title, file=dest.name, frames=len(wave), note=note,
               sha256=sha(dest), rms_dbfs=20*np.log10(np.maximum(np.sqrt(np.mean(wave**2, axis=0)), 1e-30)).tolist())
    scene['variants'].append(row)
    r['clips'].append(dict(scene=scene['key'], **row))


try:
    fit = load(consume(a.fit/'report.json'))
    audit = load(consume(a.audit/'report.json'))
    assert fit['result'] == 'fixed_centers_checked' and audit['result'] == 'passed'
    assert fit['accepted_count'] == 1 and fit['rejected_count'] == 1
    plan = load(consume(repo/'research/E_decel_source_v1_plan.json'))
    row = fit['accepted'][0]
    folder = a.fit/row['case']['name']
    old = consume(repo/'voices/cabin_anchors_v1/E Cabin Lower.model')
    _, old_root = load_dna(old)
    ratio = row['root_hz']/old_root
    command = list(map(str, [a.dna_probe, old, a.out/'old_cabin_raw.wav', plan['seconds'], ratio, 1, 1]))
    result = subprocess.run(command, cwd=repo, capture_output=True, timeout=180)
    (a.out/'old_cabin.log').write_bytes(result.stdout+result.stderr)
    r['commands'].append(dict(argv=command, exit_code=result.returncode))
    assert result.returncode == 0
    consume(a.dna_probe)
    sustained = dict(key='sustained', title='持续生成 · 同一声学音高',
                     info=f"声学根频率 {row['root_hz']:.3f} Hz · 未标定实车 RPM · 固定声线 8 秒", variants=[])
    clip(sustained, 'old', '旧车内声线 · 移至本音高', a.out/'old_cabin_raw.wav',
         '旧高转加速观察参数；同一 C OSC 核，主声线随机种子 1。录音条件不同，电平也可能不同。')
    clip(sustained, 'dna', '新减速观察 · 只听 DNA', folder/'original.wav',
         '新提取的平均相位、谐波幅度与统计起伏；同一 C OSC 核，种子 1，无素材循环。')
    for seed in plan['seeds']:
        clip(sustained, 'mix_'+str(seed), '新声线＋原细节 · 生成组 '+str(seed),
             folder/f'candidate_{seed}.wav',
             '最多撤出 35% 高频谐波功率，再补入该源窗独立拟合的连续共振细节；主 DNA 种子固定，仅细节使用本组随机序列。')
    clip(sustained, 'reference', '原声 · 定音短参考', folder/'reference.wav',
         '短窗经已有共同声学时钟归一后还原至本音高，不循环；不等于未处理原声。')
    detail = dict(key='detail', title='新增连续细节 · 独奏',
                  info='独立细节层，不包含主 DNA；同一 C 共振核持续生成', variants=[])
    for seed in plan['seeds']:
        clip(detail, 'detail_'+str(seed), '细节独奏 · 生成组 '+str(seed),
             folder/f'detail_{seed}.wav', '新随机激励与素材拟合共振，不是原音频残差回放。')
    stereo = None
    if a.stereo:
        stereo = load(consume(a.stereo/'report.json'))
        assert stereo['result'] == 'stereo_extension_rendered' and len(audit['stereo_trials']) == 3
        for seed in plan['seeds']:
            clip(sustained, 'stereo_'+str(seed), '新声线＋双声道细节 · 生成组 '+str(seed),
                 a.stereo/f'candidate_{seed}.wav',
                 '主 DNA 与原细节方案完全相同；新细节使用左右联合统计，不另加扩宽器或房间混响。')
            clip(detail, 'stereo_'+str(seed), '双声道细节独奏 · 生成组 '+str(seed),
                 a.stereo/f'detail_{seed}.wav', '双声道新随机激励与共振，保留录音通道关系的统计特征。')
    context = dict(key='context', title='素材上下文 · 未处理',
                   info='E 视频显示三挡、速度下降；同步踏板／负载／真实 RPM 未知', variants=[])
    entry = load(consume(a.workspace/'references/segments_v1.json'))['sources']['E']
    with sf.SoundFile(a.workspace/entry['master']) as stream:
        stream.seek(round(51.5*48000))
        native = stream.read(round(3.5*48000), dtype='float64', always_2d=True)
    native_path = a.out/'native_context_float.wav'
    sf.write(native_path, native, 48000, subtype='FLOAT')
    clip(context, 'native', '原始减速上下文 · 51.5–55 秒', native_path,
         '原生 48 kHz 双声道，没有音高归一；仅施加本页共同增益和边缘淡化。')
    rejected = fit['rejected'][0]
    clip(context, 'excluded', '未采用源窗 · 54 秒附近', a.fit/rejected['case']['name']/'raw_source.wav',
         '第 7 谱线独立检查未通过，未发布此处的模型或合成候选。')
    scenes = [sustained, detail, context]
    template = consume(repo/'tools/decel_source_v1/review.html')
    data = dict(scenes=scenes)
    save(a.out/'data.json', data)
    page = template.read_text(encoding='utf-8').replace('__DATA__', json.dumps(data, ensure_ascii=False))
    assert page.count('<audio ') == 1 and '__DATA__' not in page
    (a.out/'index.html').write_text(page, encoding='utf-8', newline='\n')
    (a.out/'player.js').write_text(page.split('<script>')[1].split('</script>')[0], encoding='utf-8', newline='\n')
    shutil.copy2(__file__, a.out/'executed_review.py')
    shutil.copy2(template, a.out/'executed_review.html')
    fig, axes = plt.subplots(3 if stereo else 2, 1, figsize=(10, 10 if stereo else 7), layout='constrained')
    plots = [('Old cabin shifted', a.out/'old_cabin_raw.wav'), ('New DNA', folder/'original.wav'),
             ('New DNA + original detail35', folder/'candidate_8121907.wav'), ('Source', folder/'reference.wav')]
    if stereo:
        plots.append(('New DNA + joint detail35', a.stereo/'candidate_8121907.wav'))
    for label, file in plots:
        wave, rate = sf.read(file, always_2d=True)
        if label != 'Source':
            wave = wave[plan['crop_frames']:]
        hz, power = signal.welch(wave, fs=48000, nperseg=2048, noverlap=1536, axis=0, detrend=False)
        for c, axis in enumerate(axes[:2]):
            axis.semilogx(hz, 10*np.log10(power[:, c]+1e-30), lw=.8, label=label)
    for c, axis in enumerate(axes[:2]):
        axis.set(xlim=(100, 14000), ylim=(-140, -20), xlabel='Hz', ylabel='PSD dBFS/Hz',
                 title=['Left | no per-file gain matching', 'Right | no per-file gain matching'][c])
        axis.legend(fontsize=8)
        axis.grid(alpha=.2)
    if stereo:
        bands = [v['hz'] for v in stereo['trials'][0]['short_mixed_vs_reference']]
        centers = [np.sqrt(lo*hi) for lo, hi in bands]
        for i, (old_trial, new_trial) in enumerate(zip(row['renders'], stereo['trials'])):
            assert old_trial['seed'] == new_trial['seed']
            axes[2].plot(centers, [v['complex_coherence_error'] for v in old_trial['metrics']],
                         'o-', color='#a86524', alpha=.5, label='Original detail / all seeds' if i == 0 else None)
            axes[2].plot(centers, [v['complex_coherence_error'] for v in new_trial['short_mixed_vs_reference']],
                         'o-', color='#167778', alpha=.5, label='Joint detail / all seeds' if i == 0 else None)
        axes[2].set(xscale='log', xlabel='Band center Hz', ylabel='Complex coherence difference',
                    title='Difference from source statistics | not a realism score', ylim=(0, .85))
        axes[2].legend(fontsize=8)
        axes[2].grid(alpha=.2)
    fig.savefig(a.out/'spectrum.png', dpi=130)
    plt.close(fig)
    url = 'http://127.0.0.1:8789/'+(a.out/'index.html').relative_to(a.workspace).as_posix()
    with urllib.request.urlopen(url, timeout=20) as response:
        assert response.read() == (a.out/'index.html').read_bytes()
    r.update(result='passed', url=url, common_gain=.5, edge_fade_ms=5, clip_count=len(r['clips']),
             no_per_clip_level_matching=True, human_accepted=False, runtime_changed=False,
             old_acoustic_root_hz=old_root, old_pitch_ratio=ratio, new_acoustic_root_hz=row['root_hz'])
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json', r)
