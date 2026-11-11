"""Generate a compact local listening tool and evidence-led research note."""
from pathlib import Path
import csv
import hashlib
import html
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'references/analysis/joint_stereo_v1'
base = json.loads((OUT/'results.json').read_text(encoding='utf-8'))
bands = json.loads((OUT/'band_accounting.json').read_text(encoding='utf-8'))
low = json.loads((OUT/'low_band_extension.json').read_text(encoding='utf-8'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert bands['input_results_sha256'] == sha(OUT/'results.json')
assert low['original_results_sha256'] == sha(OUT/'results.json')

LABELS = {'A_idle_check': 'A · 驻车低转 · 208–211 s',
          'A_road_check': 'A · 行驶尾排 · 316–319.5 s',
          'A_revs_explore': 'A · 驻车补油前段 · 238–242 s',
          'A_revs_check': 'A · 驻车补油后段 · 244–248 s',
          'B_pull_explore': 'B · 车内前段 · 218–222 s',
          'B_pull_check': 'B · 车内后段 · 226–230 s'}
METHODS = {'reference': '原始参考', 'legacy_independent64': '旧 OSC',
           'independent64': '新逐声道', 'joint64': '共享频率',
           'joint64_short': '共享 · 短窗', 'joint64_low28': '共享 · 低频扩展'}

table = []
player_data = {}
for name, case in base['cases'].items():
    derivatives = dict(case['auditions'], joint64_low28=low['cases'][name]['audition'])
    player_data[name] = dict(label=LABELS[name], takes={})
    for key, item in derivatives.items():
        path = ROOT/item['file']
        assert path.exists() and sha(path) == item['sha256']
        player_data[name]['takes'][key] = '../'+item['file']
    for key in list(case['methods'])+['joint64_low28']:
        metrics = low['cases'][name]['metrics'] if key == 'joint64_low28' else case['methods'][key]['metrics']
        table.append(dict(case=name, source_seconds='-'.join(map(str, case['source_seconds'])),
                          method=key, waveform_residual_db=metrics['relative_waveform_residual_db'],
                          output_to_reference_power_db=metrics['output_to_reference_power_db'],
                          full_side_to_mid_db=metrics['side_to_mid_db'],
                          high_3k_8k_side_to_mid_db=metrics['bands'][3]['side_to_mid_db'],
                          high_3k_8k_power_fraction=metrics['bands'][3]['power_fraction']))
with (OUT/'summary.csv').open('w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=list(table[0]))
    writer.writeheader()
    writer.writerows(table)

ar = base['cases']['A_revs_check']
bc = base['cases']['B_pull_check']
be = base['cases']['B_pull_explore']
def high_width(c, m):
    return (c['reference'] if m == 'reference' else c['methods'][m]['metrics'])['bands'][3]['side_to_mid_db']
def below80(name):
    return 100*sum(b['reference_power_fraction'] for b in bands['cases'][name]['reference_bands'][:2])

note = f'''# 立体声 OSC 核查 · 第一轮

当前可操作的 C 工具仍为已冻结的 V0.3。以下新增的是离线诊断和试听素材；结论将约束下一轮运行时设计。

## 结论

1. **左右分别拟合，可能制造额外宽度。** A 的 244–248 秒片段，3–8 kHz 的 Side/Mid 为 {high_width(ar, 'reference'):.2f} dB；旧逐声道 OSC 为 {high_width(ar, 'legacy_independent64'):.2f} dB；共享频率、分别保留左右幅度和相位后为 {high_width(ar, 'joint64'):.2f} dB。相位关系得到改善，但这不证明宽度越大越真实。A 行驶片段几乎为单声道，其极弱 Side 的相对误差不应直接解释成可闻效果。
2. **此前遗漏的低频不能归为噪声。** B 的 218–222 秒和 226–230 秒，分别有 {below80('B_pull_explore'):.1f}% / {below80('B_pull_check'):.1f}% 的录音能量低于原算法的 80 Hz 下限。只将候选下限扩至 28 Hz，固定 64 条共享轨迹，整体波形残差由 {be['methods']['joint64']['metrics']['relative_waveform_residual_db']:.2f} / {bc['methods']['joint64']['metrics']['relative_waveform_residual_db']:.2f} dB 变为 {low['cases']['B_pull_explore']['metrics']['relative_waveform_residual_db']:.2f} / {low['cases']['B_pull_check']['metrics']['relative_waveform_residual_db']:.2f} dB。B 后段整体 Side/Mid 参考为 {bc['reference']['side_to_mid_db']:.2f} dB，扩展后为 {low['cases']['B_pull_check']['metrics']['side_to_mid_db']:.2f} dB。低频可能同时包含发动机、结构传导、路噪和录音影响，尚未分离。
3. **全频统一缩短窗口会丢失低频分辨率。** 已知 AM/FM 控制信号从长窗的 {base['controls']['known_stereo_am_fm']['methods']['joint_4096']['metrics']['relative_waveform_residual_db']:.2f} dB 改善至短窗的 {base['controls']['known_stereo_am_fm']['methods']['joint_2048']['metrics']['relative_waveform_residual_db']:.2f} dB；但 A 后段补油反而从 {ar['methods']['joint64']['metrics']['relative_waveform_residual_db']:.2f} dB 恶化至 {ar['methods']['joint64_short']['metrics']['relative_waveform_residual_db']:.2f} dB。下一步应检查分频段的时间／频率分辨率，而非全频套同一短窗。
4. **高频缺口依片段而变。** 逐声道、共享频率和短窗方案各有取舍；共享支持在 B 中还可能把有限轨迹优先分给强低频，削弱弱高频。现有结果支持先核查轨迹分配、频率／相位估计、瞬态和频率相关传递关系，不能据总残差直接补随机嘶声。

## 方法与可复现边界

- 使用已批准 A/B 的 float32 解码主文件，保持 stereo。六个片段没有本轮高通、降噪、压缩或归一化。A 的录影视角已核查；B 无本地视频，其驾驶工况仍是音频推断。
- 全部方案最多 128 个声道振荡器输出。独立方案允许每声道 64 个频率；共享方案用 64 个共同频率，每条分别存 L/R 复幅度。这里的“64”是随时间跟踪的轨迹数，不是发动机阶次。
- 新估计器使用居中 Hann 变换、4 倍零填充、复数插值及旁瓣排除。曾发现将窗旁瓣误当 OSC 的问题；已知固定立体声音调排除后残差为 {base['controls']['sparse_stereo']['methods']['joint_4096']['metrics']['relative_waveform_residual_db']:.2f} dB。旁瓣排除也可能遮住弱邻近分音，仍需后续研究。
- 4096 / 2048 帧窗口分别为 85.3 / 42.7 ms，步长均为 256 帧。帧步长不等于事件时间精度。80 Hz 下限是最初方案；28 Hz 是观察到 B 的频带遗漏后追加的探索实验，六段使用相同参数。
- 分离的 explore/check 片段检验同一估计器在其他内容上的行为。**每段仍拟合自身，不是留出片段的生成式音色验证。** 没有学习 RPM × 负载 × 状态函数，也没有把离线轨迹直接植入 C 模型。
- 所有重建都只合成 AM/FM 正弦，未加入随机噪声或残差波形。波形残差包含带宽遗漏、非稳态、相位、轨迹分配、干涉和噪声等误差，不能当噪声比例、真实度或能力上限。
- 试听副本分别按中心区间的 stereo 非加权 RMS 对齐到 −23 dBFS，再应用同组共同峰值余量、5 ms 端点淡化、PCM24。增益逐文件记录。该处理不是 LUFS；指标来自处理前的信号。原始素材保持不变。

## 摘要数据

下表是整体波形残差 dB，数值越负表示同片段波形误差越小，不代表更真实。

| 片段 | 旧逐声道 | 新逐声道 | 共享长窗 | 共享短窗 | 共享 28 Hz |
|---|---:|---:|---:|---:|---:|
'''
for name, case in base['cases'].items():
    vals = [case['methods'][k]['metrics']['relative_waveform_residual_db'] for k in
            ['legacy_independent64', 'independent64', 'joint64', 'joint64_short']]
    vals += [low['cases'][name]['metrics']['relative_waveform_residual_db']]
    note += '| '+LABELS[name]+' | '+' | '.join(f'{v:.2f}' for v in vals)+' |\n'
note += '''
## 对 C 模块的约束

保持 `drive → voicing/orchestrator → DNA/PAD/NVH/events → spatial → output` 的职责边界。当前七种工况与六层独立包络已经落实；运动模式松油保挡、制动安全降挡也已实现。上游 V6 的控制方法和实际路径见 `V6方法论与V02实现.md`，本实验不改写上游快照。

下一轮音色改动应创建新版本：先验证低阶／高阶分开估计能否兼顾变速与分辨率，再决定如何把稳态频谱、循环变化和声道传递关系压缩成可随 RPM／负载变化的参数。车内与车外独立建模；7.1.4 继续接收十个独立声源，不能将双耳录音的左右差异直接复制到高度声道。没有实测 IR 与扬声器试听前，空间化保持工程近似。

纯 OSC 能精确表达稳定谐波，并可用随时间变化的大量正弦逼近更复杂信号；当前少量规则参数与状态映射还不足以证明“与真实 V10 一样”。可维护的运行时需要保留各物理／设计层的独立控制，而不是固化一段拟合轨迹。

## 文件

- `references/analysis/joint_stereo_v1/results.json`：主实验、设置、来源哈希、重建与试听增益。
- `band_accounting.json`：分带误差、80 Hz 以下遗漏；使用增益逆转后的 PCM24 中心区间复核原指标，差异须小于 0.002 dB。
- `low_band_extension.json`：28 Hz 下限实验；43.37 Hz 低频控制通过，交换 L/R 的输出误差为零。
- `summary.csv`：每个片段／方法的波形残差、宽度与高频比例。
- `tools/osc_research/tracker.py` 与 `metrics.py`：估计、跟踪和指标分模块维护。
- `tools/analyze_joint_stereo.py`、`finalize_joint_stereo.py`、`analyze_low_band_osc.py`：依次运行以上三步。
- `research/立体声OSC试听.html`：同时间位置切换试听。

整个驾驶声浪目标仍为 active：主观自然度、实车声纹／状态标定、降挡补油、物理 NVH／声学与未来阵列试听仍未完成。
'''
(ROOT/'research/立体声OSC核查.md').write_text(note, encoding='utf-8')

options = ''.join(f'<option value="{k}"'+(' selected' if k == 'A_revs_check' else '')+f'>{html.escape(v)}</option>'
                  for k, v in LABELS.items())
buttons = ''.join(f'<button type="button" data-method="{k}" aria-pressed="{str(k=="reference").lower()}">{v}</button>'
                  for k, v in METHODS.items())
page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>立体声 OSC · 对照试听</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#111a22;color:#deeaee;font:16px/1.7 system-ui,sans-serif}
main{max-width:900px;margin:44px auto;padding:0 24px 60px}h1{font-size:29px;line-height:1.3;margin:8px 0 18px}
h2{font-size:19px;margin:0 0 14px}.tag{font-size:13px;letter-spacing:1.5px;color:#7bd8bf}.quiet{color:#a0b5c1;font-size:14px}
section{background:#192733;border:1px solid #30434f;border-radius:13px;padding:26px;margin:24px 0}
label{display:block;font-size:14px;color:#b0c4ce;margin:0 0 8px}select{width:100%;padding:11px;background:#101b24;color:#e4eff3;border:1px solid #4b6574;border-radius:7px;font:inherit}
.methods{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin:20px 0}button{padding:12px 8px;background:#233745;border:1px solid #46616f;border-radius:7px;color:#d6e4eb;font:inherit;cursor:pointer}
button[aria-pressed=true]{background:#a7e7d2;color:#092b24;border-color:#a7e7d2}button:hover{border-color:#8cd1bf}button:focus-visible,select:focus-visible{outline:3px solid #9de2d0;outline-offset:3px}
audio{width:100%;display:block;margin:18px 0 6px}#now{font-size:16px;color:#a7e7d2;min-height:28px}a{color:#87d6c4}details{margin-top:22px}summary{cursor:pointer;color:#aac8d5}p{margin:10px 0}
@media(max-width:560px){main{margin:26px auto;padding:0 16px 40px}section{padding:18px}.methods{grid-template-columns:repeat(2,1fr)}h1{font-size:26px}}
</style><main><div class="tag">VEHICLE SOUND LAB · OFFLINE OSC STUDY</div><h1>听音色，也听左右关系</h1>
<p>这组实验比较同一段录音的纯 OSC 重建。A 是车外尾排参考，B 是另一辆车的车内双耳录音。当前可操作的驾驶工具仍为 V0.3。</p>
<section><h2>选择片段与方法</h2><label for="case">素材时间以原片为准</label><select id="case">OPTIONS</select>
<div class="methods" role="group" aria-label="重建方法">BUTTONS</div><div id="now" role="status" aria-live="polite"></div>
<audio id="player" controls preload="metadata"></audio><p class="quiet">切换方法会保留播放位置。每段均作 stereo RMS 对齐，保留段内动态；不是 LUFS 匹配。</p>
</section><p>建议先在 A 的驻车补油后段比较「旧 OSC」和「共享频率」，留意声像是否虚宽；再在 B 中比较「共享频率」和「低频扩展」，留意厚度与空间重心。</p>
<p class="quiet">长窗与短窗各有取舍。听起来更亮、更宽或数值更好，都不能单独证明更真实。</p>
<details><summary>方法与验证范围</summary><p>所有重建最多 128 个声道振荡器输出：逐声道允许左右各 64 条频率轨迹；共享方案用 64 个共同频率，并分别保留左右幅度和相位。这些轨迹数不是发动机阶次。</p>
<p>「新逐声道」用于检查频率／相位估计改进；「共享频率」进一步约束左右频率支持；「短窗」提高时间分辨率；「低频扩展」将候选下限从 80 Hz 改为 28 Hz，保留长窗。</p>
<p>每段拟合自身。它们没有加入噪声或残差采样，尚未转换成随油门和转速运行的车辆模型。参考原音和已冻结版本均保留。</p></details>
<p><a href="立体声OSC核查.md">核查记录与结论</a> · <a href="V03试听.html">V0.3 驾驶与状态分层试听</a> · <a href="../references/analysis/joint_stereo_v1/summary.csv">数据表</a></p>
</main><script>
const data=DATA, names=NAMES;
const audio=document.getElementById('player'), selector=document.getElementById('case'), status=document.getElementById('now');
let method='reference', serial=0;
function load(preserve){
 const token=++serial, position=preserve?audio.currentTime:0, playing=preserve&&!audio.paused;
 audio.pause();audio.src=data[selector.value].takes[method];
 status.textContent=data[selector.value].label+' · '+names[method];
 audio.onloadedmetadata=()=>{if(token!==serial)return;audio.currentTime=Math.min(position,Math.max(0,audio.duration-.02));if(playing)audio.play().catch(()=>{});};
 for(const b of document.querySelectorAll('[data-method]'))b.setAttribute('aria-pressed',b.dataset.method===method?'true':'false');
 audio.load();
}
selector.addEventListener('change',()=>load(false));
for(const b of document.querySelectorAll('[data-method]'))b.addEventListener('click',()=>{method=b.dataset.method;load(true);});
load(false);
</script></html>'''
page = page.replace('OPTIONS', options).replace('BUTTONS', buttons).replace('DATA', json.dumps(player_data, ensure_ascii=False)).replace('NAMES', json.dumps(METHODS, ensure_ascii=False))
(ROOT/'research/立体声OSC试听.html').write_text(page, encoding='utf-8')
print('Written listening page, research note and 30-row summary CSV.')
