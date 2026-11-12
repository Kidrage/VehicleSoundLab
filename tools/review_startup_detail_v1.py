"""Publish same-A startup source/detail and unified-state C comparisons."""
import argparse,html,json,re,shutil,subprocess,sys
from pathlib import Path
from urllib.parse import quote,urljoin
from urllib.request import urlopen
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
p.add_argument('--ffmpeg',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha,read

a.out.mkdir(parents=True,exist_ok=False);(a.out/'audio').mkdir();shutil.copy2(__file__,a.out/'executed_review.py')
r=dict(result='running',clips=[],human_accepted=False,browser_interaction_checked=False)
try:
    root=a.workspace/'references/analysis/startup_detail_v1/render1'
    proof=json.loads((root/'report.json').read_text(encoding='utf-8'))
    assert proof['result']=='unified_C_detail_candidate_rendered'
    r['render_report_sha256']=sha(root/'report.json')
    fit=a.workspace/'references/analysis/startup_detail_v1/fit1'
    def audio(path):
        y,rate=sf.read(path,always_2d=True);assert rate==48000;return y
    reference=audio(fit/'reference_float.wav')
    base=audio(root/'renders/hold_48271_0_raw.wav')[96000:]
    cloud=audio(root/'renders/hold_48271_1_residual_raw.wav')[96000:]
    context,r['approved_input']=read(a.workspace,'A_start_context','audio_onset_observation')
    cases=[('reference','固定音高录音短参考',reference,'同A 38.48–39.51秒，经共同慢坐标归一化。短参考，不循环扩长。'),
        ('base','持续 DNA · 原版',base,'实际C持续生成的后8秒，保留原DNA。'),
        ('detail50','持续 DNA＋细节50%',base+.5*cloud,'只加同A平均谱矩细节，未改变DNA或低频。'),
        ('detail100','持续 DNA＋细节100%',base+cloud,'11个可独立叠加频带；600–850Hz保持原样。'),
        ('solo','只听细节层 · 100%',cloud,'固定Hz密集正弦OSC，不含PCM循环或额外幅度调制。'),
        ('context','A实录 · 启动语境',context,'33–40秒原时序；C仍采用工程启动时长，不是同步复刻。')]
    for amount in (0,1):
        cases.append((f'starts{amount}',f'同一C驾驶链 · 细节{amount*100}%',
            audio(root/'renders'/f'starts_2_{amount:.1f}_mix.wav'),
            '两次启动；启动前段50%、接火低频50%、相同驾驶轨迹。混音保留0.25主增益。'))
    cards=[]
    for key,title,y,note in cases:
        y=y.copy()*.5;n=min(240,len(y)//2)
        y[:n]*=np.linspace(0,1,n)[:,None];y[-n:]*=np.linspace(1,0,n)[:,None]
        assert np.isfinite(y).all() and np.max(abs(y))<.9
        path=a.out/'audio'/f'{key}.wav';sf.write(path,y,48000,subtype='PCM_24')
        done=subprocess.run([str(a.ffmpeg),'-v','error','-i',str(path),'-f','null','-'],capture_output=True,timeout=30)
        assert done.returncode==0,done.stderr
        r['clips'].append(dict(key=key,sha256=sha(path),frames=len(y),peak=float(np.max(abs(y))),FFmpeg_decodes=True))
        rel='../references/analysis/startup_detail_v1/'+a.out.name+'/audio/'+path.name
        cards.append('<article><strong>'+html.escape(title)+'</strong><p>'+html.escape(note)+'</p><audio controls preload="metadata" src="'+rel+'"></audio></article>')
    body='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>启动车内细节 V1</title>
<style>body{font:16px/1.65 system-ui;max-width:840px;margin:30px auto;padding:0 18px;background:#f5f6f6;color:#20282b}h1{font-size:25px}article{background:white;border:1px solid #dce1e3;border-radius:8px;padding:14px 16px;margin:12px 0}audio{width:100%;height:42px}article p,.note{color:#566269;font-size:14px}</style>
<h1>启动车内细节 V1</h1><p>暂停其他发声窗口。先比较前四条，再比较最后两条完整启停。这里只补同A启动车内的平均细节，尚未替换原生监听窗口。</p>
<p>共同0.5增益与5ms首尾淡化，无逐条响度补偿、EQ、压缩或限幅。前五条是声源单位；最后两条另有0.25主增益和工况包络，不能跨组按整体响度判断。</p>'''+''.join(cards)+'''
<p class="note">C持续生成新的声音，没有原片段循环。独立叠加未通过的600–850Hz未强行补入；快速接火音高、时间变化和完整状态仍缺。训练统计接近不代表音色通过；新候选未获听评、设备或实际7.1.4验收。</p>
<p><a href="接火低频统一驾驶V1.html">接火低频对照</a> · <a href="状态素材与系统回放V1.html">其他状态素材</a></p>
<script>document.querySelectorAll('audio').forEach(a=>a.addEventListener('play',()=>document.querySelectorAll('audio').forEach(b=>{if(a!==b)b.pause()})))</script></html>'''
    page=a.workspace/'research/启动车内细节V1.html';assert not page.exists()
    page.write_text(body,encoding='utf-8',newline='\n');shutil.copy2(page,a.out/'page.html')
    url='http://127.0.0.1:8789/research/'+quote(page.name)
    with urlopen(url,timeout=15) as response:assert response.read()==page.read_bytes()
    for rel in re.findall(r'<audio[^>]*src="([^"]+)"',body):
        with urlopen(urljoin(url,rel),timeout=15) as response:assert response.read()==(a.out/'audio'/Path(rel).name).read_bytes()
    r.update(result='pass',page=url,page_sha256=sha(page),HTTP_bytes_verified=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],page=r.get('page'),clips=len(r['clips']))))
