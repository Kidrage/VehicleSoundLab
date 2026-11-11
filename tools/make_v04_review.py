"""Create V0.4 listening comparison and explain what the measurements prove."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'renders/v0.4.0'
r=json.loads((OUT/'verification.json').read_text())
m=json.loads((ROOT/'references/analysis/multires_v1/results.json').read_text())
LABELS={'drive':'完整运动模式驾驶 · 30 秒','lift':'固定转速收油／再加油 · 7.5 秒',
        'shifts':'手动换挡与停机 · 13 秒','850':'850 RPM · 怠速台架',
        '2500':'2500 RPM · 重载台架','5000':'5000 RPM · 重载台架',
        '8000':'8000 RPM · 重载台架','pure5000':'5000 RPM · Pure OSC 台架'}
data={key:dict(label=LABELS[key],takes={version:'../renders/v0.4.0/'+case[version]['audition']['file']
                                      for version in ['v03','v04']}) for key,case in r['cases'].items()}
options=''.join(f'<option value="{key}">{label}</option>' for key,label in LABELS.items())
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>V0.4 · 高频与缸列相位试听</title><style>
*{box-sizing:border-box}body{margin:0;background:#111a22;color:#dfeaf0;font:16px/1.7 system-ui,sans-serif}main{max-width:900px;margin:42px auto;padding:0 24px 60px}
h1{font-size:30px;line-height:1.3;margin:8px 0 20px}.tag{color:#88d8c0;font-size:13px;letter-spacing:1px}h2{font-size:19px;margin:0 0 14px}
section{margin:24px 0;padding:26px;border:1px solid #31434f;border-radius:14px;background:#192733}.quiet{font-size:14px;color:#a0b6c2}
select{width:100%;font:inherit;color:#e3eff3;background:#111d27;border:1px solid #4b6574;border-radius:7px;padding:11px}label{font-size:14px;display:block;margin-bottom:8px;color:#bed0d9}
.buttons{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:18px 0}button{font:inherit;padding:12px;background:#233745;color:#deebee;border:1px solid #496674;border-radius:8px;cursor:pointer}
button[aria-pressed=true]{background:#a7e7d2;color:#092b24;border-color:#a7e7d2}button:focus-visible,select:focus-visible{outline:3px solid #a7e7d2;outline-offset:3px}
#now{color:#a7e7d2;min-height:28px}audio{display:block;width:100%;margin:16px 0}p{margin:10px 0}a{color:#8ad9c5}details{margin:22px 0}summary{cursor:pointer;color:#b0cbd8}
@media(max-width:550px){main{padding:0 16px 40px;margin-top:26px}section{padding:18px}h1{font-size:27px}}
</style><main><div class="tag">VEHICLE SOUND LAB · 0.4.0</div><h1>高频连续性与两缸列的关系</h1>
<p>本版细化 V10 的高阶谐波，并让它与 DNA 层使用一致的缸列延时。主界面的操控保持简洁；进入 Sound detail，用 High firing orders 调节这部分细节。</p>
<section><h2>同一驾驶轨迹，新旧版本切换</h2><label for="case">试听场景</label><select id="case">OPTIONS</select>
<div class="buttons" role="group" aria-label="版本"><button data-method="v03" aria-pressed="false">V0.3 · 冻结参考</button><button data-method="v04" aria-pressed="true">V0.4 · 新高阶声源</button></div>
<div id="now" role="status" aria-live="polite"></div><audio id="player" controls preload="metadata"></audio>
<p class="quiet">切换保留时间位置。每对试听副本按整段 stereo 非加权 RMS 对齐，保留段内动态；不是 LUFS 匹配。源导出另存。</p></section>
<p>先听 2500 RPM 的颗粒与连续性，再听 8000 RPM 是否过亮、刺耳。Pure OSC 场景便于听谐波部分；完整驾驶用于判断同一高阶声源在启动、升挡、收油与制动降挡中的表现。</p>
<p class="quiet">两版使用完全相同的车辆状态轨迹，均采用运动模式松油保挡、制动安全降挡。当前仍是工程音色，兰博基尼声纹标定和听感验收继续进行。</p>
<details><summary>这次改了什么</summary><p>V10 从 24 个稀疏高阶位置，改为有效频带内连续的缸列谐波；根据转速、14 kHz 上界和采样率裁剪，幅度平滑变化。左右共享燃烧时钟，保留交替点火关系和 DNA 层相同的延时参数。</p>
<p>高阶频谱配置、振荡器、机械／进气细节分别维护。其他四个模板保留原算法，实际导出与 V0.3 逐字节一致。独立声源和 7.1.4 渲染接口继续保留。</p>
<p>新增高阶声源测试验证连续谐波、相位关系、采样率边界和用户 DNA 旁路。设备测试向声卡提交静音，验证实时合成与调度，不代替实际扬声器听音。</p></details>
<p><a href="V04高阶声源实现.md">实现与验证记录</a> · <a href="V03试听.html">V0.3 工况分层</a> · <a href="立体声OSC试听.html">离线立体声重建研究</a></p>
<p class="quiet">启动可调参程序：E:\\VehicleSoundLab\\Launch.cmd。反馈请注明版本、场景和时间点，尤其是高频是否更像发动机、是否变得嘶亮，以及收油时是否过薄。</p>
</main><script>
const data=DATA,names={v03:'V0.3',v04:'V0.4'};
const audio=document.getElementById('player'),selector=document.getElementById('case'),status=document.getElementById('now');
let method='v04',serial=0;
function load(preserve){const token=++serial,position=preserve?audio.currentTime:0,playing=preserve&&!audio.paused;audio.pause();audio.src=data[selector.value].takes[method];status.textContent=data[selector.value].label+' · '+names[method];
audio.onloadedmetadata=()=>{if(token!==serial)return;audio.currentTime=Math.min(position,Math.max(0,audio.duration-.02));if(playing)audio.play().catch(()=>{});};
for(const b of document.querySelectorAll('[data-method]'))b.setAttribute('aria-pressed',b.dataset.method===method?'true':'false');audio.load();}
selector.addEventListener('change',()=>load(false));for(const b of document.querySelectorAll('[data-method]'))b.addEventListener('click',()=>{method=b.dataset.method;load(true);});load(false);
</script></html>'''.replace('OPTIONS',options).replace('DATA',json.dumps(data,ensure_ascii=False))
(ROOT/'research/V04试听.html').write_text(page,encoding='utf-8')
note=f'''# V0.4 高阶声源实现与验证

运行核心版本为 0.4.0，默认入口 `Launch.cmd`，本轮单独构建在 `build-v04`，旧 `build` 和冻结 V0.3 保留。新窗口标题含版本，避免与已打开的旧版窗口混淆。

## 为什么改

上一轮立体声研究发现，独立声道拟合会放大微弱的 Side，遗漏 80 Hz 以下的内容还会影响厚度与整体宽度。高频残差同时包含估计误差和非周期成分，不能全部用随机噪声填满。

本轮双分辨率实验用 4096 帧分析低频、2048 帧分析高频，在 800–1600 Hz 交叉，并保留独立 L/R 复幅度。已知 AM/FM 信号从长窗 {m['controls']['moving_am_fm']['long28']['relative_waveform_residual_db']:.2f} dB 改善至 {m['controls']['moving_am_fm']['multi64']['relative_waveform_residual_db']:.2f} dB；固定立体声音调为 {m['controls']['fixed_stereo']['multi64']['relative_waveform_residual_db']:.2f} dB。真实六段录音的整体误差改善仍小，部分反而略差，频带配额也未带来普遍优势。它验证了分析分辨率的取舍，尚未解决真实引擎生成。详细数据为 `references/analysis/multires_v1/results.json`；各段仍拟合自身，不能称为留出音色生成测试。

代码核查另发现：旧高阶模块只有 24 个稀疏位置；其额外相位调制和左右关系也未采用 DNA 的缸列延时。运行时因此先修复这两个具体问题。双窗的逐帧拟合轨迹没有作为运行时数据使用。

## 模块

- `src/core/high_orders.c`：V10 共用燃烧时钟的连续缸列高阶谐波；左右保持交替点火相位，并使用 DNA 相同的延时秒数。幅度每 128 帧更新、8 ms 平滑；逐样本用三角递推求和。每缸列最多 512 阶，低于原 128 个 720° 分音上界的成分不重复添加，最高 14 kHz，并有随采样率变化的边界保护。
- `src/profiles/high_orders.c/.h`：频谱中心、宽度、密度补偿、增益和过渡区独立配置。现有数值仍为工程参数，不是 Lamborghini 实测系数。
- `src/core/high_order_types.h`：振荡器幅度状态。与驾驶、事件、空间及 UI 分开。
- `src/core/mechanical.c`：原机械与进气细节迁入独立模块，本轮保留其声音算法；两条固定机械成分尚未变成实测结构共振模型。
- `src/core/detail.c`：其余四模板的旧高阶算法。没有把 V10 的等间隔缸列假设套给 crossplane V8。
- `tests/test_high_orders.c`：实际合成后的连续高阶频点与左右相位检验、用户 DNA 旁路、采样率边界。

仍保留 V0.3 的七种运行工况与六层独立包络。高阶输出消费自己的工况与换挡包络；高阶声音进入左右排气对象。十个 pre-master 声源、车辆坐标和 7.1.4 文件接口保持一致。非整数比率本身不是错误；这里修正的是同一燃烧源的层间关系。

## 实际文件与验证

五项 CTest 全部通过，JUnit 为 `renders/v0.4.0/ctest.xml`。新增测试在合成输出上检查连续高阶和相位关系；原测试覆盖种子、块大小、五模板启动、驾驶状态、分层包络、关闭与 stereo／12 声道声源一致性。

八组新旧音频使用同一宿主输入；八组驾驶 CSV 逐字节一致。其余四模板各做 4000 RPM 导出，新旧 WAV 也逐字节一致。原始导出保留，试听副本按组作明示的 RMS 对齐。

| 稳定场景 | 3–8 kHz 新减旧 | 8–14 kHz 新减旧 |
|---|---:|---:|
'''
for key in ['850','2500','5000','8000','pure5000']:
    rows=r['cases'][key]['spectrum']['new']
    note+=f"| {LABELS[key]} | {rows[4]['new_minus_old_db']:+.2f} dB | {rows[5]['new_minus_old_db']:+.2f} dB |\n"
d=r['device']
note+=f'''
频段测量区间为文件 3–5.975 秒，测量原始导出电平。高频能量增加只证明声音变化进入了文件，不证明自然度提高。

设备 smoke test：512 帧／10.67 ms 缓冲，平均合成 {d['render_ms_mean']:.2f} ms，最大 {d['render_ms_max']:.2f} ms；墙钟 {d['wall_seconds']:.4f} s、设备进度 {d['device_seconds']:.4f} s，队列耗空 {d['queue_empty_observations']} 次。提交设备的是静音，内部执行完整合成，用于检查实时开销与设备时钟，未做声卡环回或实际扬声器验收。

7.1.4 样例 `renders/v0.4.0/drive_714_v04.wav` 为 float32 speaker bed，通道顺序 FL FR FC LFE BL BR SL SR TFL TFR TBL TBR；独立 mono float32 源在 `stems`，位置说明为 `drive_714_scene.json`。它没有封装 Atmos 对象，也未在物理阵列试听。

## 尚未完成

持续音色与收油、换挡的真实感仍需听音；尚无 RPM／负载遥测，所有高阶增益、延时和状态时间均不能称为实车标定。后续需要更可靠的视频／音频事件标签、RPM × 负载谱形、降挡补油与离合衔接、真实机械／气流残差和实测声学。代码核查还发现，导入合成器 DNA 时，根音相位与其他层消费的发动机相位仍共用 control.phase，后续应分离；现有纯谐波互换测试不证明多层混合路径已经物理独立。更多谐波与正确的层间相位只是可核查的结构改进，整个驾驶声浪目标仍为 active。
'''
(ROOT/'research/V04高阶声源实现.md').write_text(note,encoding='utf-8')
print('Written V04 listening page and implementation evidence.')
