"""Publish verified stationary exterior anchors and a shared-gain listening page."""
import argparse
import html
import json
from pathlib import Path
import shutil
import sys
from urllib.parse import quote

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
args = parser.parse_args()
repository = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import sha

root = args.workspace/'references/analysis/exterior_clock_v1'
anchors = root/'anchors_v2'
driving = root/'driving'
build = json.loads((anchors/'build.json').read_text(encoding='utf-8'))
verified = json.loads((driving/'verification.json').read_text(encoding='utf-8'))
assert verified['result'] == 'pass' and verified['accepted'] is False
assert sha(anchors/'build.json') == verified['build_sha256']
for mapping in (build['source_sha256'], verified['source_sha256']):
    for name, expected in mapping.items():
        assert sha(repository/name) == expected, name
assert sha(repository/'handoff-build/bin/Release/VslAtlasDrive_probe.exe') == verified['probe_sha256']

page = args.workspace/'research/驻车车外四锚点V1.html'
bank = repository/'voices/exterior_anchors_v1'
review = root/'review'
assert not page.exists() and not bank.exists() and not review.exists()
bank.mkdir()
review.mkdir()
records, voices, cards = [], [], []


def audition(source, name, gain, first=0, stop=None):
    audio, rate = sf.read(source, always_2d=True)
    assert rate == 48000 and audio.shape[1] == 2
    end = len(audio) if stop is None else round(stop*rate)
    audio = audio[round(first*rate):end].copy()*gain
    assert len(audio) >= 480 and np.isfinite(audio).all() and abs(audio).max() < .98
    fade = np.linspace(0, 1, 240)
    audio[:240] *= fade[:, None]
    audio[-240:] *= fade[::-1, None]
    target = review/(name+'.wav')
    sf.write(target, audio, rate, subtype='PCM_24')
    records.append(dict(name=name, source=str(source.relative_to(root)), source_sha256=sha(source),
        source_start_seconds=first, source_stop_seconds=stop, gain=gain,
        file=target.name, sha256=sha(target), frames=len(audio),
        processing='Common total gain0.5,5ms endpoint fades,PCM24; no per-clip normalization/EQ'))
    url = '../'+target.relative_to(args.workspace).as_posix()
    return f'<audio controls preload="metadata" src="{quote(url, safe="/.")}"></audio>', len(audio)/rate


labels = ['低转情境', '较低中转', '较高中转', '高转情境']
for i, row in enumerate(build['anchors']):
    origin = anchors/row['name']
    assert sha(origin/'voice.model') == row['model_sha256']
    filename = row['name']+'.model'
    shutil.copy2(origin/'voice.model', bank/filename)
    voices.append(dict(name=row['name'], file=filename, model_sha256=row['model_sha256'],
        base_hz=row['base_hz'], modeled_top_hz=row['modeled_top_hz'], source='A',
        segment_id=build['source']['segment_id'], seconds=row['phase_polish']['source_seconds'],
        perspective='stationary rear exterior mixed recording', analysis_cycles=4,
        harmonics=288, components=12, reference_order=row['phase_polish']['reference_order'],
        status='experimental; human listening pending', lf_model=None))
    reference, duration = audition(origin/'fixed_reference_float.wav', f'anchor{i}_reference', .5)
    expected = next(r for r in row['render'] if r['pitch'] == 1.)['sha256']
    assert sha(origin/'raw_1.0.wav') == expected
    generated, _ = audition(origin/'raw_1.0.wav', f'anchor{i}_osc', .5, 1, 7)
    cards.append(f'<article><h3>{labels[i]} · 根频率 {row["base_hz"]:.2f} Hz</h3>'
        f'<div class="pair"><div><label>录音短参考 · {duration:.2f} 秒</label>{reference}</div>'
        f'<div><label>持续 OSC · 6 秒</label>{generated}</div></div></article>')

bank_index = dict(schema='vsl.exterior-anchor-bank/1', renderer='modules/sound_dna and modules/dna_atlas',
    source_build_sha256=sha(anchors/'build.json'), catalog_sha256=build['source']['catalog_sha256'],
    voices=voices, driving_root_per_rpm=1/120,
    driving_mapping_status='Explicit engineering hypothesis only; no independent A RPM measurement',
    limits=verified['limits']+['Keep distinct from accepted A moving close-tailpipe DNA/LF and E cabin anchors',
        'First anchor stops near2.9kHz; common harmonic count and missing inharmonic detail constrain bandwidth'])
(bank/'index.json').write_text(json.dumps(bank_index, ensure_ascii=False, indent=2), encoding='utf-8')

driving_cards = []
for name, label in [('neutral', '空挡补油 · 8 秒'), ('auto', '自动驾驶 · 30 秒'),
                    ('downshift', '升降挡与制动 · 18 秒')]:
    row = next(r for r in verified['runs'] if r['name'] == name)
    source = driving/(name+'_render.wav')
    assert sha(source) == row['files_sha256'][source.name]
    audio, _ = audition(source, name, 1)
    driving_cards.append(f'<article><h3>{label}</h3>{audio}</article>')

trace = np.genfromtxt(driving/'auto_trace.csv', delimiter=',', names=True)
t = trace['seconds']
fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True, layout='constrained')
roots = [v['base_hz'] for v in voices]
axes[0].axhspan(roots[0], roots[-1], color='#37a677', alpha=.14, label='Anchor bracket only')
axes[0].axhspan(roots[0], roots[1], color='#d29641', alpha=.20, label='Sparse low / mid gap')
axes[0].plot(t, trace['root_hz'], color='#2b4561', lw=1, label='OSC acoustic clock')
for value in roots:
    axes[0].axhline(value, color='#737b83', lw=.5, ls=':')
axes[0].set_ylabel('Root Hz')
axes[0].set_title('A stationary rear context | RPM /120 is an explicit uncalibrated hypothesis')
axes[0].legend(fontsize=8, loc='upper right')
axes[1].plot(t, trace['envelope'], color='#733f85', lw=1, label='State gain envelope')
axes[1].set_ylabel('Gain')
axes[1].legend(fontsize=8)
axes[2].step(t, trace['gear'], where='post', lw=1, label='Controller gear')
axes[2].set(ylabel='Gear', xlabel='Time (s)', yticks=range(8))
for ax in axes:
    ax.set_xlim(0, 30)
    ax.grid(alpha=.16)
figure = review/'drive_trace.png'
fig.savefig(figure, dpi=150)
plt.close(fig)

page.write_text('''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>驻车车外 DNA · 四锚点 V1</title>
<style>body{font:16px/1.65 system-ui,sans-serif;max-width:860px;margin:28px auto;padding:0 20px;background:#f4f5f5;color:#222b30}h1{font-size:25px}h2{font-size:20px;margin-top:28px}h3{font-size:16px;margin:0 0 10px}article{background:white;border:1px solid #dce1e3;border-radius:8px;padding:16px;margin:14px 0}.pair{display:grid;grid-template-columns:1fr 1fr;gap:18px}.pair>div{min-width:0}label{display:block;font-size:14px;color:#525e65;margin-bottom:7px}audio{width:100%;height:42px}img{width:100%}details{margin-top:24px}@media(max-width:600px){.pair{grid-template-columns:1fr}body{padding:0 14px}}</style></head><body>
<h1>驻车车外 DNA · 四锚点 V1</h1>
<p>先比较每档录音参考与持续 OSC，再听空挡补油，判断声线是否自然、转速变化时是否突然变声或出现拍频。</p>
<p>本组来自 A 的同一驻车尾部录音位置；与你已认可的移动尾排 DNA／低频配方分别保存。参考已校正为该档稳定音高，保留实际短时长；生成声持续产生新的细节，不循环录音。</p>
<p>所有音频使用相同总增益，没有逐条补响度。低转档仍缺较高频细节，低转与中转之间的素材锚点较稀疏。本轮尚未加入独立低频／进气／噪音层。</p>
<h2>四档声线</h2>'''+''.join(cards)+'''<h2>同一声源的驾驶变化</h2>
<p>先听空挡补油，再听驾驶过渡。当前转速映射采用暂定比例，不能视为实测车辆转速还原。</p>'''+''.join(driving_cards)+f'''
<details><summary>锚点范围与驾驶记录</summary><img alt="声源根频率、工况增益与挡位" src="../{figure.relative_to(args.workspace).as_posix()}">
<p>绿色仅表示位于首尾锚点之间，橙色表示较大的锚点间隔；均不代表每个转速、负载和状态已有实录覆盖。根频率不是已确认的曲轴频率。</p></details>
<script>document.querySelectorAll('audio').forEach(a=>a.addEventListener('play',()=>document.querySelectorAll('audio').forEach(b=>{{if(b!==a)b.pause()}})))</script></body></html>''', encoding='utf-8')
report = dict(schema='vsl.exterior-review/1', accepted=False, records=records,
    build_sha256=sha(anchors/'build.json'), validation_sha256=sha(driving/'verification.json'),
    bank_index_sha256=sha(bank/'index.json'), page=str(page), page_sha256=sha(page),
    figure_sha256=sha(figure), builder_sha256=sha(__file__))
(review/'review.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(dict(page=str(page), bank=str(bank), audio_files=len(records)), ensure_ascii=False))
