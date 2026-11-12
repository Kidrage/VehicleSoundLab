"""Publish actual unified-C exports and an explicitly labeled functional take."""
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
r=dict(result='running',clips=[],human_accepted=False,browser_interaction_checked=False)
try:
    root=a.workspace/'references/analysis/catch_drive_v1/verification1';proof=json.loads((root/'report.json').read_text())
    assert proof['result']=='integrated_catch_function_pass';r['verification_sha256']=sha(root/'report.json')
    x,meta=read(a.workspace,'A_start_context','audio_onset_observation');r['input']=meta
    def audio(path):
        y,rate=sf.read(path,always_2d=True);assert rate==48000;return y
    cases=[('reference','A实录 · 启动语境',x,'33–40秒车内原时序。C仍沿用工程启停时长，未与原视频同步。')]
    for amount in (0,.5,1):
        key=f'catch_2_{amount:.1f}'
        cases.append((f'mix{int(amount*100)}',f'统一C · 接火低频{int(amount*100)}%',audio(root/'renders'/(key+'_mix.wav')),
            '相同A趋稳DNA、启动前段50%、同一驾驶器，两次启动。原生研究窗口调用相同底层。'))
    cases.append(('solo','只听接火低频 · 100%',audio(root/'renders/catch_2_1.0_catch_bloom.wav')*.25,
        '保持混音中的0.25主增益，不额外放大独奏。'))
    cases.append(('take','行程自包含回放 · 功能检查',audio(root/'take_2.wav'),
        '设备录制后清空外部模型，再从文件重建；包含高转、声层和空间切换，仅用于功能检查，不作实录音色复刻。'))
    cards=[]
    for key,title,y,note in cases:
        y=y.copy()*.5;n=min(240,len(y)//2);y[:n]*=np.linspace(0,1,n)[:,None];y[-n:]*=np.linspace(1,0,n)[:,None]
        assert np.isfinite(y).all() and np.max(abs(y))<.9
        path=a.out/'audio'/(key+'.wav');sf.write(path,y,48000,subtype='PCM_24')
        done=subprocess.run([str(a.ffmpeg),'-v','error','-i',str(path),'-f','null','-'],capture_output=True,timeout=30);assert done.returncode==0,done.stderr
        r['clips'].append(dict(key=key,sha256=sha(path),frames=len(y),peak=float(np.max(abs(y))),FFmpeg_decodes=True))
        relative='../references/analysis/catch_drive_v1/'+a.out.name+'/audio/'+path.name
        cards.append('<article><strong>'+html.escape(title)+'</strong><p class="note">'+html.escape(note)+'</p><audio controls preload="metadata" src="'+relative+'"></audio></article>')
    body='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>接火低频统一驾驶 V1</title>
<style>body{font:16px/1.65 system-ui;max-width:840px;margin:30px auto;padding:0 18px;background:#f5f6f6;color:#20282b}h1{font-size:25px}article{background:white;border:1px solid #dce1e3;border-radius:8px;padding:14px 16px;margin:12px 0}audio{width:100%;height:42px}.note{color:#566269;font-size:14px}</style>
<h1>接火低频统一驾驶 V1</h1><p>暂停其他发声窗口。这里是实时系统底层的实际导出；本轮验证接入一致性，没有新拟合音色。</p>
<p>本地运行 Launch-Catch-Study.cmd：默认停止、接火低频0%。先开始监听、点火；在“声层量”右侧选“接火低频”，调至50%或100%后熄火、再次点火比较。可用原来的录制／保存／载入按钮回放。</p>'''+''.join(cards)+'''
<p class="note">共同0.5增益和5ms首尾淡化，无逐条响度匹配、压缩或限幅。前五条C保留0.25主增益；实录与C整体响度不同。最后一条是不同控制的功能行程，不能比较其音色优劣。</p>
<p class="note">新声层是持续DNA的固定滤波成分，遵循同一CATCH状态，只向FL/FR路由一次。快速接火音高／高频仍缺，未获听评或长期／实际7.1.4验收。旧播放器和已认可的车外配方保留。</p>
<p><a href="接火低频建立V1.html">上一轮离线音色候选</a> · <a href="状态素材与系统回放V1.html">其他状态素材</a></p>
<script>document.querySelectorAll('audio').forEach(a=>a.addEventListener('play',()=>document.querySelectorAll('audio').forEach(b=>{if(a!==b)b.pause()})))</script></html>'''
    page=a.workspace/'research/接火低频统一驾驶V1.html';assert not page.exists();page.write_text(body,encoding='utf-8',newline='\n');shutil.copy2(page,a.out/'page.html')
    url='http://127.0.0.1:8789/research/'+quote(page.name)
    with urlopen(url,timeout=15) as response:assert response.read()==page.read_bytes()
    for relative in re.findall(r'<audio[^>]*src="([^"]+)"',body):
        with urlopen(urljoin(url,relative),timeout=15) as response:assert response.read()==(a.out/'audio'/Path(relative).name).read_bytes()
    r.update(result='pass',page=url,page_sha256=sha(page),HTTP_bytes_verified=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],page=r.get('page'),clips=len(r['clips']))))
