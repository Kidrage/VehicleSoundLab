"""Publish same-A cabin settling source and two-start unified-C previews."""
import argparse,html,json,re,shutil,subprocess,sys
from pathlib import Path
from urllib.parse import quote,urljoin
from urllib.request import urlopen
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--ffmpeg',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import read,sha
a.out.mkdir(parents=True,exist_ok=False);(a.out/'audio').mkdir();shutil.copy2(__file__,a.out/'executed_review.py')
r=dict(result='running',clips=[],source_sha256=sha(__file__),human_accepted=False,browser_interaction_checked=False)
try:
    build=a.workspace/'references/analysis/startup_catch_v1/render1';proof=json.loads((build/'report.json').read_text(encoding='utf-8'))
    assert proof['result']=='same_A_cabin_candidate_rendered';r['render_report_sha256']=sha(build/'report.json')
    x,meta=read(a.workspace,'A_start_context','audio_onset_observation');r['input']=meta
    actual=x[round((38.48-33)*48000):round((39.51-33)*48000)]
    def audio(path):
        y,rate=sf.read(path,always_2d=True);assert rate==48000;return y
    cases=[('context','A实录 · 启动语境',x,'车内33–40秒，含完整启动过程。'),
           ('settle','A实录 · 启动后趋稳段',actual,'车内38.48–39.51秒，是本轮DNA提取的局部范围。'),
           ('fixed_reference','同段实录 · 固定音高参考',audio(build/'fixed_reference_float.wav'),'离线统一了较慢的音高变化，保留左右声道；这是处理后的录音参考。'),
           ('C','C持续DNA · 8秒',audio(build/'renders/fixed_1.0.wav'),'使用同一Sound DNA算法持续生成，未循环原片段。先比较上条参考的声线与厚度。'),
           ('state0','同一C驾驶链 · 两次启停',audio(build/'renders/scene_2_0.0_mix.wav'),'本轮A车内DNA，关闭启动机械附加层。现有生命周期控制音高与包络；快速接火声纹未按录音拟合。'),
           ('state50','同一C驾驶链 · 加入启动前段',audio(build/'renders/scene_2_0.5_mix.wav'),'相同A车内DNA，启动前段附加量50%。两次启停使用同一驾驶器；仅作衔接预览。')]
    cards=[]
    for key,title,y,note in cases:
        y=y.copy()*.5;fade=min(240,len(y)//2)
        y[:fade]*=np.linspace(0,1,fade)[:,None];y[-fade:]*=np.linspace(1,0,fade)[:,None]
        assert np.isfinite(y).all() and np.max(abs(y))<.9
        path=a.out/'audio'/(key+'.wav');sf.write(path,y,48000,subtype='PCM_24')
        done=subprocess.run([str(a.ffmpeg),'-v','error','-i',str(path),'-f','null','-'],capture_output=True,timeout=30)
        assert done.returncode==0,done.stderr
        r['clips'].append(dict(key=key,sha256=sha(path),frames=len(y),peak=float(np.max(abs(y))),common_gain=.5,FFmpeg_decodes=True))
        url='../references/analysis/startup_catch_v1/'+a.out.name+'/audio/'+path.name
        cards.append('<article><strong>'+html.escape(title)+'</strong><p class="note">'+html.escape(note)+'</p><audio controls preload="metadata" src="'+url+'"></audio></article>')
    body='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>启动后车内 DNA V1</title><style>body{font:16px/1.65 system-ui;max-width:850px;margin:30px auto;padding:0 18px;background:#f5f6f6;color:#20282b}h1{font-size:25px}article{background:white;border:1px solid #dce1e3;border-radius:8px;padding:14px 16px;margin:12px 0}audio{width:100%;height:42px}.note{color:#566269;font-size:14px}</style>
<h1>启动后车内 DNA V1</h1><p>先暂停其他发声窗口。先比较“固定音高参考”和“C持续DNA”，再听两次启停预览。</p>
<p>本轮启动前段和运行DNA都取自A车内录音。快速接火、低频冲起和完整启动仍需继续完善。</p>'''+''.join(cards)+'''
<p class="note">六条共同0.5增益、5ms首尾淡化，没有逐条响度匹配、EQ或压缩。后两条另含C系统原有0.25主音量及工况包络，响度较低，不能与前四条按响度判断音色优劣。DNA的300Hz以上仍有频带亏损；不把模型中全部低音归为独立车体声源。</p>
<p class="note">启停时长、转速曲线和声学音高到RPM的映射沿用工程策略；不是按原录音复刻。当前只验证趋稳段较慢的共同音高变化，未识别真实曲轴转速。候选没有替换默认窗口或已认可车外音色。</p>
<p><a href="启动层与统一驾驶V1.html">上一轮启动前段对照</a> · <a href="状态素材与系统回放V1.html">全部状态参考</a></p>
<script>document.querySelectorAll('audio').forEach(a=>a.addEventListener('play',()=>document.querySelectorAll('audio').forEach(b=>{if(a!==b)b.pause()})))</script></html>'''
    page=a.workspace/'research/启动后车内DNAV1.html';assert not page.exists();page.write_text(body,encoding='utf-8',newline='\n');shutil.copy2(page,a.out/'page.html')
    url='http://127.0.0.1:8789/research/'+quote(page.name)
    with urlopen(url,timeout=15) as response:assert response.read()==page.read_bytes()
    for relative in re.findall(r'<audio[^>]*src="([^"]+)"',body):
        with urlopen(urljoin(url,relative),timeout=15) as response:assert response.read()==(a.out/'audio'/Path(relative).name).read_bytes()
    r.update(result='pass',page=url,page_sha256=sha(page),HTTP_bytes_verified=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],page=r.get('page'),clips=len(r['clips']))))
