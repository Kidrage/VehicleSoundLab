"""Publish startup source comparison and an explicitly mixed-context drive preview."""
import argparse
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import quote, urljoin
from urllib.request import urlopen

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--ffmpeg', type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import read, sha

root = a.workspace / 'references/analysis/startup_drive_v1'
verified = root / 'verification1'
proof = json.loads((verified / 'report.json').read_text(encoding='utf-8'))
assert proof['result'] == 'integrated_startup_function_pass'
a.out.mkdir(parents=True, exist_ok=False)
(a.out / 'audio').mkdir()
(a.out / 'renders').mkdir()
shutil.copy2(__file__, a.out / 'executed_review.py')
r = dict(result='running', source_sha256=sha(__file__),
         verification_sha256=sha(verified / 'report.json'), clips=[],
         human_accepted=False, browser_interaction_checked=False)
try:
    case = json.loads((a.workspace / 'references/analysis/stereo_bed_v1/before/report.json').read_text(encoding='utf-8'))['cases'][2]
    probe = verified / 'bin/VslAtlasDrive_probe.exe'
    assert sha(probe) == proof['binary_sha256'][probe.name]
    # Same seed, driver, amounts and oscillator kernel; only the optional model differs.
    prefix = a.out / 'renders/E_static'
    cmd = [str(v) for v in [probe, *case['models'][:2], prefix, *case['options'],
           '--stereo-bed', '1', '--startup-profile', repo / 'voices/start_texture_v1/A cabin early.start',
           '--startup-gain', '.5']]
    done = subprocess.run(cmd, cwd=repo, capture_output=True, timeout=180)
    (a.out / 'render.log').write_bytes(done.stdout + done.stderr)
    assert done.returncode == 0
    r['command'] = cmd
    context, meta = read(a.workspace, 'A_start_context', 'audio_onset_observation')
    r['input'] = meta
    reference = context[round((36.65-33)*48000):round((37.12-33)*48000)]
    static, rate = sf.read(prefix.with_name(prefix.name + '_startup.wav'), always_2d=True)
    motion, rate2 = sf.read(verified / 'renders/E_startup_startup.wav', always_2d=True)
    full, rate3 = sf.read(verified / 'renders/E_startup_render.wav', always_2d=True)
    assert rate == rate2 == rate3 == 48000
    assert static.shape == motion.shape == full.shape
    r['render_input_sha256'] = {str(v): sha(v) for v in [prefix.with_name(prefix.name + '_startup.wav'),
        verified / 'renders/E_startup_startup.wav', verified / 'renders/E_startup_render.wav']}
    cases = [
        ('context', 'A 实录 · 完整启动语境', context, 'A车内33–40秒；含其他机械、燃烧与空间声音。'),
        ('early', 'A 实录 · 启动前段', reference, '36.65–37.12秒，用于提取前后半段的谱功率与左右关系。'),
        ('static', 'C 附加层独奏 · 单一平均谱形', static, '同一驾驶器CRANK门控，独立量50%。'),
        ('motion', 'C 附加层独奏 · 前后谱形过渡', motion, '保持载波频率与相位连续，只过渡谱功率／左右关系；门控与独立量同上。'),
        ('full', 'C 统一链试听 · A启动层＋E运行车内DNA', full,
         '用来检查同一控制器下的启动与运行衔接。A／E车型与录音不同，尚未拟合接火低频，不是上方实录的全声还原。'),
    ]
    cards = []
    for key, title, signal, note in cases:
        y = signal.copy() * .5
        fade = min(240, len(y)//2)
        y[:fade] *= np.linspace(0, 1, fade)[:, None]
        y[-fade:] *= np.linspace(1, 0, fade)[:, None]
        assert np.isfinite(y).all() and np.max(abs(y)) < .9
        path = a.out / 'audio' / (key + '.wav')
        sf.write(path, y, 48000, subtype='PCM_24')
        decode = subprocess.run([str(a.ffmpeg), '-v', 'error', '-i', str(path), '-f', 'null', '-'],
                                capture_output=True, timeout=30)
        assert decode.returncode == 0, decode.stderr
        r['clips'].append(dict(key=key, title=title, note=note, frames=len(y),
            common_gain=.5, peak=float(np.max(abs(y))), sha256=sha(path), FFmpeg_decodes=True))
        url = '../references/analysis/startup_drive_v1/' + a.out.name + '/audio/' + path.name
        cards.append('<article><strong>'+html.escape(title)+'</strong><p class="note">'+html.escape(note)+
                     '</p><audio controls preload="metadata" src="'+url+'"></audio></article>')
    body = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>启动层与统一驾驶 V1</title><style>body{font:16px/1.65 system-ui;max-width:850px;margin:30px auto;padding:0 18px;background:#f5f6f6;color:#20282b}h1{font-size:25px}article{background:white;border:1px solid #dce1e3;border-radius:8px;padding:14px 16px;margin:12px 0}audio{width:100%;height:42px}.note{color:#566269;font-size:14px}</style>
<h1>启动层与统一驾驶 V1</h1><p>先暂停其他发声窗口。先听实录前段，再比较两条C附加层；最后听统一链的衔接。</p>
<p>这版补充启动前段的谱形变化。完整启动的接火、低频建立和运行声线还需继续拟合。</p>'''
    body += ''.join(cards)
    body += '''<p class="note">全页共同0.5增益和5ms首尾淡化，没有逐条响度补偿、EQ或压缩。实录含完整混合声，C独奏只含300–8000Hz的启动附加层。两条C独奏同一50%层量，但不同谱形可能有响度差，不能仅据此判定更真实。</p>
<p class="note">拖转门控沿用0.28秒工程策略；前后谱形随归一化进度连续过渡。没有复制实录时间包络、PCM或录音循环，未把混合谱峰解释为真实电机扫频。</p>
<p><a href="状态素材与系统回放V1.html">其他状态实录与系统功能回放</a> · <a href="驻车状态局部对照V1.html">驻车低转／补油降转局部对照</a></p>
<script>document.querySelectorAll('audio').forEach(a=>a.addEventListener('play',()=>document.querySelectorAll('audio').forEach(b=>{if(a!==b)b.pause()})))</script></html>'''
    page = a.workspace / 'research/启动层与统一驾驶V1.html'
    assert not page.exists()
    page.write_text(body, encoding='utf-8', newline='\n')
    shutil.copy2(page, a.out / 'page.html')
    url = 'http://127.0.0.1:8789/research/' + quote(page.name)
    with urlopen(url, timeout=15) as response:
        assert response.read() == page.read_bytes()
    for relative in re.findall(r'<audio[^>]*src="([^"]+)"', body):
        with urlopen(urljoin(url, relative), timeout=15) as response:
            assert response.read() == (a.out / 'audio' / Path(relative).name).read_bytes()
    r.update(result='listening_page_published', page=url, page_sha256=sha(page), HTTP_bytes_verified=True)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    (a.out / 'report.json').write_text(json.dumps(r, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps(dict(result=r['result'], page=r.get('page'), clips=len(r['clips'])), ensure_ascii=True))
