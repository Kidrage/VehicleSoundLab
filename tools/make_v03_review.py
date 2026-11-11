"""Local listening page; media paths point to verified local exports."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'renders/v0.3.0'
report=json.loads((DATA/'verification.json').read_text(encoding='utf-8'))
assert report['version']=='0.3.0'


def player(label,file,pair=''):
    assert (DATA/file).exists(),file
    return f'<div class="take"><strong>{label}</strong><audio controls preload="metadata" data-pair="{pair}" src="../renders/v0.3.0/{file}"></audio></div>'


html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>V0.3 · 状态与分层试听</title><style>
body{background:#101820;color:#d9e5ed;font:16px/1.65 system-ui,sans-serif;margin:0}
main{max-width:940px;margin:40px auto;padding:0 24px 64px}h1{font-size:30px;line-height:1.3}h2{font-size:21px;margin:0 0 12px}
.tag{color:#71cfbc;font-size:14px}.muted{color:#9fb1c0;font-size:14px}section{background:#192530;border:1px solid #2b3b47;border-radius:14px;margin:22px 0;padding:24px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:18px}.take{margin:12px 0}strong{display:block;margin-bottom:7px}audio{width:100%;height:42px}a{color:#75d5c1}img{max-width:100%;border-radius:8px}
details{margin-top:18px}summary{cursor:pointer;color:#9fc3d3}@media(max-width:650px){.pair{grid-template-columns:1fr}main{margin-top:24px}}
</style><main><div class="tag">VEHICLE SOUND LAB · 0.3.0</div><h1>让各层跟随发动机工况变化</h1>
<p>本版细化启动、加速、收油和换挡时各层的起落。先听完整驾驶，再用固定转速收油和空挡补油判断变化是否自然。当前仍是 V10 工程模型，尚未完成兰博基尼声纹标定。</p>
<p class="muted">试听副本均标明电平处理。下面的合成试听使用整段非加权 RMS 对齐，保留段内动态；这不是 LUFS 匹配。原始导出另存。播放任一段会暂停其他段；同组新旧版切换时保留进度。</p>
<section><h2>01 · 相同踏板场景，新旧版比较</h2><p>关注启动后机体的重量感、加速中的进气与高频细节，以及松油、换挡时是否仍像整段声音一起被拉小。</p><div class="pair">'''
html+=player('V0.2 · 原冻结版本','audition_drive_v02.wav','drive')
html+=player('V0.3 · 分层工况包络','audition_drive_v03.wav','drive')
html+='''</div><p class="muted">两版使用同一自动踏板程序。V0.3 按你选定的运动模式松油保挡、制动时安全降挡，换挡和转速轨迹因此与旧版不同；稳定转速比较放在第 04 组。</p></section>
<section><h2>02 · 固定 5000 RPM，快速收油再加油</h2><p>约 3 秒切到负负载，约 4.8 秒重新加负载。转速保持不变，便于单独判断进气先收、机体保持、排气和气流衰减的层次。</p>'''
html+=player('V0.3 · 收油／再加油 · RMS 对齐','audition_lift_v03.wav')
html+='''<p class="muted">这是转速／负载台架诊断，不能当作整车驾驶记录。</p><details><summary>查看控制包络与独立声源</summary><img src="../renders/v0.3.0/v10_lift.png" alt="分层控制与换挡门控曲线"><p class="muted">曲线是控制量，各层按自身峰值显示；下面是主输出前的原始单声源，保留相对电平。</p>'''
for title,key in [('排气左','exhaust_left'),('机体','body'),('进气','intake'),('气流左','air_left'),('瞬态事件','events')]:
    html+=player(title,f'stems/v10_lift_{key}.wav')
html+='''</details></section><section><h2>03 · 空挡补油与实际换挡</h2><p>空挡场景由油门驱动转速，车辆保持不动。手动场景包含启动、加速、两次升挡、收油、制动降挡和停机。</p>'''
html+=player('空挡补油 · RMS 对齐','audition_neutral_v03.wav')
html+=player('手动换挡与停机 · RMS 对齐','audition_shifts_v03.wav')
html+='''<details><summary>查看换挡时各层的控制量</summary><img src="../renders/v0.3.0/v10_shifts.png" alt="换挡状态与各层独立门控"></details></section>
<section><h2>04 · 稳定重载音色</h2><p>同样 5000 RPM、+0.85 负载。用这组判断持续音色，和前面的瞬态表现分别评价。</p><div class="pair">'''
html+=player('V0.2 · RMS 对齐','audition_loaded_v02.wav','loaded')
html+=player('V0.3 · RMS 对齐','audition_loaded_v03.wav','loaded')
html+='''</div></section><section><h2>参考与文件</h2><p>已批准的 Performante 驻车补油片段，用于听感对照。录音视角、转速和负载与合成场景没有逐点对齐，电平也不直接可比。</p>
<audio controls preload="metadata" src="../references/clean/A_corsa_tailpipe_blips.wav"></audio>
<p class="muted">参考切片保留原有固定余量、28 Hz 高通和端点淡化，没有本轮归一化处理。</p>
<p><a href="../renders/v0.3.0/v10_drive.wav">原始 stereo 导出</a> · <a href="../renders/v0.3.0/v10_drive_714.wav">7.1.4 WAV</a> · <a href="../renders/v0.3.0/v10_drive_714_scene.json">声源与通道说明</a></p>
<p class="muted">7.1.4 为扬声器声床 WAV，独立声源另存。当前应用监听为 stereo；尚未完成真实 7.1.4 扬声器阵列试听。</p></section>
<p class="muted">反馈时请指出具体场景和时间，优先描述：持续音色像不像、收油是否过薄／拖尾过长、换挡是否抽空、高频是否刺耳、左右声场是否自然。数值验证不代替这项听感判断。</p></main>
<script>
const items=[...document.querySelectorAll('audio')];
for(const item of items)item.addEventListener('play',()=>{
  for(const other of items)if(other!==item&&!other.paused){
    if(item.dataset.pair&&item.dataset.pair===other.dataset.pair&&other.currentTime<item.duration)item.currentTime=other.currentTime;
    other.pause();
  }
});
</script></html>'''
(ROOT/'research/V03试听.html').write_text(html,encoding='utf-8')
print('Written research/V03试听.html')
