"""One-player diagnostic of existing C acceleration; no new timbre selection."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.request import urlopen

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--analysis', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from drive_evidence_v1.sources import sha
from listening_v1.page import make_page

a.out.mkdir(parents=True, exist_ok=False)
r = dict(schema='vsl.acceleration-passage-review/1', result='running', clips=[], source_sha256={})
try:
    report = json.loads((a.analysis/'report.json').read_text(encoding='utf-8'))
    assert report['result'] == 'current_C_source_diagnostic_pass_only'
    r['analysis_sha256'] = sha(a.analysis/'report.json')
    for path in [Path(__file__), repo/'tools/listening_v1/page.py']:
        dest = a.out/'exact_sources'/path.relative_to(repo)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        r['source_sha256'][path.relative_to(repo).as_posix()] = sha(path)
    versions = dict(reference='原录音 · 车内第5挡加速', single_anchor='当前 C · 单锚点对照', two_anchors='当前 C · 双锚点')
    bands = dict(whole=None, low=[28,120], middle=[400,1200], high=[3000,8000])
    labels = dict(whole='完整声音', low='28–120 Hz', middle='400–1200 Hz', high='3–8 kHz')
    manifest = {v:{} for v in versions}
    for name in versions:
        path = a.analysis/f'{name}.wav'
        assert sha(path) == report['output_sha256'][path.name]
        x, rate = sf.read(path, always_2d=True)
        assert rate == 48000 and x.shape == (96000,2) and np.isfinite(x).all()
        for band, limits in bands.items():
            y = x.copy()
            if limits:
                taps = signal.firwin(2049, limits, fs=48000, pass_zero=False)
                y = signal.fftconvolve(y, taps[:, None], mode='same', axes=0)
            y *= report['plan']['common_listening_gain']
            fade = np.sin(np.linspace(0,np.pi/2,240))**2
            y[:240] *= fade[:,None]
            y[-240:] *= fade[::-1,None]
            assert abs(y).max() < .95
            file = a.out/f'{name}_{band}.wav'
            sf.write(file,y,48000,subtype='PCM_24')
            url = 'http://127.0.0.1:8789/'+file.relative_to(a.workspace).as_posix()
            with urlopen(url,timeout=10) as response:
                assert response.read() == file.read_bytes()
            done = subprocess.run(['ffmpeg','-v','error','-i',str(file),'-f','null','-'],capture_output=True,timeout=30)
            assert done.returncode == 0
            manifest[name][band+'_short'] = file.name
            r['clips'].append(dict(file=file.name,sha256=sha(file),frames=len(y),HTTP_FFmpeg_pass=True))
    page = make_page('固定挡位加速 · 当前 C 核查',
        '这页说明现有系统能生成什么，以及仍缺少什么。它是当前声源诊断，不是新优化音色或验收结论。',
        ['E的89.6–91.6秒车内录音；附近第5挡、仪表车速持续上升，踏板／真实负载和精确RPM未知。',
         '同一C Sound DNA／atlas：单锚点对照只改变音高；双锚点还连续改变谐波声线。两者均持续OSC生成，没有播放原片。',
         '统一0.5增益、5ms首尾淡化；无逐条响度补偿、房间、额外低频或细节层。录音为完整混合声，C为DNA单层。',
         '两锚点来自同段训练；音色覆盖仅约60.63–64.85Hz，越界使用端点声线，音高继续变化。不能代表全RPM加速标定。',
         '冻结粗声学轨迹仅用作离线测试输入，不是真实曲轴遥测，也未替换唯一驾驶控制器。行驶35%和低转候选保留。'],
        versions,labels,dict(short='同一段加速 · 2秒'),manifest,'reference')
    (a.out/'index.html').write_text(page,encoding='utf-8',newline='\n')
    js = page.split('<script>',1)[1].split('</script>',1)[0]
    (a.out/'player.js').write_text(js,encoding='utf-8',newline='\n')
    done = subprocess.run(['node','--check',str(a.out/'player.js')],capture_output=True,timeout=15)
    (a.out/'javascript_syntax.log').write_bytes(done.stdout+done.stderr)
    assert done.returncode == 0 and page.count('<audio ') == 1 and len(r['clips']) == 12
    url = 'http://127.0.0.1:8789/'+(a.out/'index.html').relative_to(a.workspace).as_posix()
    with urlopen(url,timeout=10) as response:
        assert response.read() == (a.out/'index.html').read_bytes()
    r.update(result='review_technical_pass_only',url=url,page_sha256=sha(a.out/'index.html'),
             manual_browser_interaction=False,new_question_sent=False,human_accepted=False,
             one_player=True,common_gain=.5,per_file_loudness_compensation=False)
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    raise
finally:
    (a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],clips=len(r['clips']),url=r.get('url'))))
