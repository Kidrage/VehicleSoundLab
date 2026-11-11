"""Explain the common-pin change and expose measured, reproducible audition."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'renders/v0.6.0'
r=json.loads((OUT/'verification.json').read_text())
labels={'850':'850 RPM · 工程怠速','1200':'1200 RPM · 低转对照','2500':'2500 RPM · 重载',
        '5000':'5000 RPM · 重载','8000':'8000 RPM · 高转重载','pure5000':'5000 RPM · Pure OSC stereo',
        'pure5000_mono':'5000 RPM · Pure OSC 合成输出折为 mono','drive':'完整运动自动挡 · 30 秒',
        'neutral':'驻车空挡补油 · 8 秒','downshift':'闭油门制动降挡 · 18 秒'}
data={key:dict(label=label,takes={v:'../renders/v0.6.0/'+r['cases'][key][v]['audition']['file'] for v in ['v05','v06']},
               gains={v:r['cases'][key][v]['audition']['gain_db'] for v in ['v05','v06']}) for key,label in labels.items()}
options=''.join(f'<option value="{key}">{label}</option>' for key,label in labels.items())
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>V0.6 · 5.2 V10 点火间隔</title><style>
*{box-sizing:border-box}body{margin:0;background:#111a22;color:#dfeaf0;font:16px/1.7 system-ui,sans-serif}main{max-width:900px;margin:40px auto;padding:0 24px 60px}
h1{font-size:29px;line-height:1.4;margin:8px 0 20px}.tag{color:#88d8c0;font-size:13px;letter-spacing:1px}h2{font-size:19px;margin:0 0 14px}
section{margin:24px 0;padding:26px;border:1px solid #31434f;border-radius:14px;background:#192733}.quiet{font-size:14px;color:#a0b6c2}
select{width:100%;font:inherit;color:#e3eff3;background:#111d27;border:1px solid #4b6574;border-radius:7px;padding:11px}label{font-size:14px;display:block;margin-bottom:8px;color:#bed0d9}
.buttons{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:18px 0}button{font:inherit;padding:12px;background:#233745;color:#deebee;border:1px solid #496674;border-radius:8px;cursor:pointer}
button[aria-pressed=true]{background:#a7e7d2;color:#092b24;border-color:#a7e7d2}button:focus-visible,select:focus-visible{outline:3px solid #a7e7d2;outline-offset:3px}
#now{color:#a7e7d2;min-height:28px}audio{display:block;width:100%;margin:16px 0}p{margin:10px 0}a{color:#8ad9c5}img{width:100%;border-radius:8px}details{margin:22px 0}summary{cursor:pointer;color:#b0cbd8}
@media(max-width:550px){main{padding:0 16px 40px;margin-top:26px}section{padding:18px}h1{font-size:25px}}
</style><main><div class="tag">VEHICLE SOUND LAB · 0.6.0</div><h1>先改对点火间隔</h1>
<p>当前 V10 采用 5.2 L 共用曲柄销的 90°／54° 交替点火。低阶、高阶排气和气流脉冲使用同一缸列关系，改变了哪些谐波相互加强或抵消。</p>
<section><h2>同一驾驶轨迹，比较点火模型</h2><label for="case">场景</label><select id="case">OPTIONS</select>
<div class="buttons" role="group" aria-label="版本"><button data-method="v05" aria-pressed="false">V0.5 · 均匀点火</button><button data-method="v06" aria-pressed="true">V0.6 · 共用曲柄销</button></div>
<div id="now" role="status" aria-live="polite"></div><audio id="player" controls preload="metadata"></audio><p id="gain" class="quiet"></p>
<p class="quiet">切换保留播放位置。九个原始渲染场景的驾驶日志完全一致；mono 是其中一组纯合成输出的折叠副本。各组明示整段 stereo 非加权 RMS 增益，保留段内动态。</p></section>
<p>建议从 2500 RPM 听中低频颗粒，再听 8000 RPM 的密度与刺耳程度。Pure OSC 的 stereo／mono 两项可检查两缸列相加后的变化。当前仍需你判断声音是否更自然。</p>
<section><h2>素材中的驻车低转</h2><p class="quiet">Performante A，原视频 208–211 秒；车外尾排视角，绝对 RPM 未知。此处保留之前切片的固定 −6.02 dB 余量、28 Hz 高通与 5 ms 端点淡化，没有响度匹配。它提供听感背景，不能与上面的 850／1200 RPM 当作已对齐测量。</p>
<audio data-reference controls preload="metadata" src="../references/clean/A_idle_context_v02.wav"></audio></section>
<details><summary>为什么更改这个基础假设</summary><p>Audi 官方 5.2 FSI 技术说明明确记录共用曲柄销和 54°／90° 点火间隔。Lamborghini 5.2 L 家族的公开说明也支持这一结构。旧版等间隔 72° 适用于另一类 V10，不能覆盖所有 V10。</p>
<p class="quiet">本次采用的是发动机家族证据；尚未取得这台 Performante 的曲轴图或缸压测量。排气管路、两侧传播时差和共振参数仍为工程值。录音的频谱间距也不能独立证明点火角度或绝对 RPM。</p><img src="../references/analysis/bank_geometry_v1/geometry_and_recordings.png" alt="均匀点火和共用曲柄销的时序、理想谐波干涉及参考录音的独立观测"></details>
<p class="quiet">运动模式松油保挡、制动降挡补油、六层独立包络、导入 DNA 与十个空间声源继续保留。更正确的几何关系仍需配合谱形、循环差异、机械／气流和真实声学标定。</p>
<p><a href="V06点火几何与素材核查.md">实现、来源和验证</a> · <a href="V05试听.html">V0.5 换挡对照</a> · <a href="立体声OSC试听.html">离线立体声研究</a></p>
<p class="quiet">可操作程序：E:\\VehicleSoundLab\\Launch.cmd。反馈可注明场景与秒数，尤其是中低频是否更有发动机颗粒、高转是否仍像规则合成音。</p>
</main><script>
const data=DATA,names={v05:'V0.5',v06:'V0.6'};
const audio=document.getElementById('player'),selector=document.getElementById('case'),status=document.getElementById('now');let method='v06',serial=0;
function load(preserve){const token=++serial,position=preserve?audio.currentTime:0,playing=preserve&&!audio.paused;audio.pause();audio.src=data[selector.value].takes[method];status.textContent=data[selector.value].label+' · '+names[method];
document.getElementById('gain').textContent='本试听副本增益 '+data[selector.value].gains[method].toFixed(2)+' dB；整段 RMS 对齐至 −23 dBFS，按组共同留峰值余量；未做 LUFS 匹配。';
audio.onloadedmetadata=()=>{if(token!==serial)return;audio.currentTime=Math.min(position,Math.max(0,audio.duration-.02));if(playing)audio.play().catch(()=>{});};
for(const b of document.querySelectorAll('[data-method]'))b.setAttribute('aria-pressed',b.dataset.method===method?'true':'false');audio.load();}
selector.addEventListener('change',()=>load(false));for(const b of document.querySelectorAll('[data-method]'))b.addEventListener('click',()=>{method=b.dataset.method;load(true);});load(false);
for(const p of document.querySelectorAll('audio'))p.addEventListener('play',()=>{for(const other of document.querySelectorAll('audio'))if(other!==p)other.pause();});
</script></html>'''.replace('OPTIONS',options).replace('DATA',json.dumps(data,ensure_ascii=False))
(ROOT/'research/V06试听.html').write_text(page,encoding='utf-8')
d=r['device']
note=f'''# V0.6 点火几何与素材核查

当前核心 0.6.0，单独构建 `build-v06`，入口 `Launch.cmd`。0.1～0.5 冻结保留。本版主要改 V10 的燃烧几何，不以增加随机噪声填平整个录音残差。

## 证据改变了什么

[Audi 官方 2021 年 5.2 FSI 技术页](https://www.audi-mediacenter.com/en/the-sheer-joy-of-driving-redefined-audi-r8-v10-performance-rwd-until-2024-14405/the-engine-legendary-ten-cylinder-on-the-road-and-the-racetrack-14408) 与 [2019 年 Engine 技术页](https://www.audi-mediacenter.com/en/the-audi-r8-until-2024-updated-dynamics-for-the-high-performance-sports-car-11734/engine-11738) 都明确写出：共用曲柄销，点火间隔交替 54°／90°，点火顺序 1-6-5-10-2-7-3-8-4-9。已保存完整 HTML、文本、访问时间和 SHA256，原段落在 `references/analysis/bank_geometry_v1/technical_evidence.json`。

[Lamborghini V10 家族的二级说明](https://en.wikipedia.org/wiki/Lamborghini_V10) 区分 5.0 L split-pin 均匀 72° 与 5.2 L non-split 90°／54°。其引述的 Evo 页面当前印有 90°／58°，五对会合计 740°，与四冲程 720° 不符；本版采用 Audi 官方明确给出的 54°，不复制该数值。原计划查看的 990193 培训 PDF 镜像失效，未取得或使用 PDF 内容。

这证明之前将“V10”一律作为均匀点火不适合 5.2 common-pin 家族。它没有证明 Performante 每根歧管的传递、录音中的缸列相位或声压，更不是从 YouTube 声音反推出缸压。本版采用家族级结构证据；这台 Performante 的曲轴图／缸压仍未核查。参数名称保持工程模型，不声称完成目标车声纹标定。

## 音频与视频核查

`tools/analyze_bank_geometry.py` 读取批准的 A/B float32 主文件，按左右声道功率平均统计，不折叠 B。A 208–211 s 的粗频谱梳状间距候选约 51.5 Hz，244–248 s 约 50 Hz，同时存在子谐波／倍频候选。8192 帧 Welch 的频率 bin 为 5.86 Hz，0.25 Hz 搜索网格不代表该精度。早期补油、行驶段与 B 混合声场的整段频谱不可据此认定单一发动机音高，得分也不是置信概率。

未把这些候选换算成“测得 RPM”，未据此修改 850 RPM 默认怠速。试听中的 1200 RPM 只是另一工程测试点。视频新增抽样 239、241、243、245、247 s，联系表在分析目录；用于核查驻车尾部视角，没有踏板、N 挡、精确 RPM 或完全无剪辑的证明。

参考切片继续使用原来的 A 208–211 s PCM24，处理与哈希已有 provenance；本轮没有新增清洗或归一化。A/B 原始来源、立体声主文件和旧研究快照完整保留。

## C 模块

- `src/profiles/firing.c/.h`：时间角度独立于音色包络和传播时差。V10 事件为 0、90、144、234、288、378、432、522、576、666 度；两缸列各隔 144°，总周期 720°。事件索引表示发生先后，不假称实车缸号。第一缸列取 0、第二缸列取 90° 是模型方位约定，具体左右管路仍待测。
- `core/dna.c`：低阶 720° 傅里叶系数消费该时序；原传播延时以秒另加，没有用一个固定秒数冒充点火角度。
- `core/high_orders.c`：第二缸列相位从半个缸列周期改为 90/144 个周期，与低阶一致。
- `core/nvh.c`：V10 第二侧气流脉冲使用同样的几何相位与时间延时。气流噪声本身仍是简化模型，不是从录音分离出的真实气流。
- `tests/test_firing.c`：720° 闭合、缸列间距、理想对偶谐波干涉、实际低阶 DNA 输出的相位；已有高阶输出测试同步核对新几何。相位隔离测试关闭循环 AM，以免把有意侧带误当几何误差。

继承 V6 的驾驶→工况→分层→事件→空间职责边界。已核查上游 `v10_powertrain.gendsp` 的右缸列使用半周期位移，且其参考场景为 Ferrari；不能把该几何原样当作所有 V10。当前机械两固定正弦、谱形、NVH、默认 0.38 ms 缸列延时、循环不平衡和 IR 仍是工程近似，未一并冒充实测模型。

## 验证

八项 CTest 通过：原 DSP、驾驶、状态包络、高阶、独立时钟、换挡、空间，以及新增点火几何。JUnit 在 `renders/v0.6.0/ctest.xml`。九个原始场景的新旧驾驶 CSV 逐字节一致；额外 mono 项由 Pure OSC stereo 算术折叠并显式匹配 RMS，共十组、20 个 PCM24 试听副本。其他四模板各 4000 RPM WAV 逐字节一致；导入工程 DNA 的 Pure OSC 路径也逐字节一致。

`tools/verify_v06.py` 另读取实际导出的左右排气 float32 声源，在固定 5000 RPM 的 3–5.5 秒窗投影到缸列频率的 1–45 阶中的 15 个检查点。旧／新版相对于各自几何加 0.38 ms 工程延时的最大相位误差分别约 0.000042／0.000030 rad，高阶检查点也有实际能量。这证明导出声源消费了配置，不能证明真实车辆的缸列相位。完整数值在 `renders/v0.6.0/workspace_audit.json`。

已知稳定谐波 WAV→DNA→当前 runtime 互换通过，主峰约 219.33 Hz，拟合残差 −84.63 dB；不能延伸为 Serum 完整音色或引擎自然度结论。

设备内部完整 DSP 的平均耗时 {d['render_ms_mean']:.4f} ms／512 帧，最大 {d['render_ms_max']:.4f} ms；墙钟 {d['wall_seconds']:.4f} s、设备 {d['device_seconds']:.4f} s，队列耗空 {d['queue_empty_observations']}。设备提交静音；未进行可听回放或声卡环回验收。十个 float32 独立声源、7.1.4 speaker bed 与坐标继续输出，阵列试听仍待进行。

## 继续工作的边界

几何修正改善的是模型依据，听感是否改善仍需试听。下一步仍是 RPM×负载×状态谱形、循环差异、燃油切断／残余激励、机械与气流激励、管腔与声场传递；已有录音尚不足以唯一分离这些参数。完整驾驶声浪目标保持 active。
'''
(ROOT/'research/V06点火几何与素材核查.md').write_text(note,encoding='utf-8')
print('Written V06 review and implementation/source record.')
