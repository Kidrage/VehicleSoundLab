"""Publish common-gain source reference / C LF bloom comparisons."""
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
    render=a.workspace/'references/analysis/catch_bloom_v1/render1';proof=json.loads((render/'report.json').read_text())
    assert proof['result']=='C_candidate_render_and_isolation_pass';r['render_report_sha256']=sha(render/'report.json')
    x,meta=read(a.workspace,'A_start_context','audio_onset_observation');r['input']=meta
    def audio(path):
        y,rate=sf.read(path,always_2d=True);assert rate==48000;return y
    cases=[('reference','A实录 · 启动语境',x,'原车内33–40秒。先听低频如何建立；C时序尚未与它对齐。'),
           ('reference_low','A实录 · 低频增强语境',x[round(4.22*48000):round(5.18*48000)],'原37.22–38.18秒，仍是完整混合录音，没有低通或源分离。')]
    for amount in (0,.5,1):
        key=f'2_{amount:.1f}';path=render/'renders'/(key+'_mix.wav')
        cases.append((f'mix{int(amount*100)}',f'C两次启停 · 新增低频{int(amount*100)}%',audio(path),
            '相同DNA、启动前段50%、驾驶器与音量。重点比较0.43–1.08秒和3.48–4.13秒；包含其后的短衰减。'))
    cases.append(('delta','只听新增低频 · 100%',audio(render/'renders/2_1.0_bloom.wav')*.25,
        '使用混音中相同的0.25主增益，没有额外放大独奏。来自DNA的固定滤波成分，不是新噪声或素材循环。'))
    cards=[]
    for key,title,y,note in cases:
        y=y.copy()*.5;n=min(240,len(y)//2)
        y[:n]*=np.linspace(0,1,n)[:,None];y[-n:]*=np.linspace(1,0,n)[:,None]
        assert np.isfinite(y).all() and np.max(abs(y))<.9
        path=a.out/'audio'/(key+'.wav');sf.write(path,y,48000,subtype='PCM_24')
        done=subprocess.run([str(a.ffmpeg),'-v','error','-i',str(path),'-f','null','-'],capture_output=True,timeout=30)
        assert done.returncode==0,done.stderr
        r['clips'].append(dict(key=key,sha256=sha(path),frames=len(y),peak=float(np.max(abs(y))),FFmpeg_decodes=True))
        relative='../references/analysis/catch_bloom_v1/'+a.out.name+'/audio/'+path.name
        cards.append('<article><strong>'+html.escape(title)+'</strong><p class="note">'+html.escape(note)+'</p><audio controls preload="metadata" src="'+relative+'"></audio></article>')
    body='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>接火低频建立 V1</title>
<style>body{font:16px/1.65 system-ui;max-width:840px;margin:30px auto;padding:0 18px;background:#f5f6f6;color:#20282b}h1{font-size:25px}article{background:white;border:1px solid #dce1e3;border-radius:8px;padding:14px 16px;margin:12px 0}audio{width:100%;height:42px}.note{color:#566269;font-size:14px}</style>
<h1>接火低频建立 V1</h1><p>先暂停其他发声窗口。重点比较三条C混音，判断低频冲起是否更像发动机，有无闷胀、嗡鸣或硬敲感。</p>
<p>同一A车内DNA，新增声层由持续DNA经固定共振带生成，受唯一驾驶器的CATCH状态调度。这里是离线C候选，未替换原生窗口。</p>'''+''.join(cards)+'''
<p class="note">全部试听共同0.5增益、5ms首尾淡化，没有逐条响度补偿、EQ、压缩或限幅。C原主增益0.25保留，参考与C的整体响度不构成音色优劣结论。新增层约98／381Hz为本段观察的宽带颜色，不是实测物理共振。</p>
<p class="note">本轮只补低频增强。快速接火音高仍沿用工程驾驶策略，时长0.65秒与实录不同；共同包络不能复现各频带完整时序，300Hz以上的DNA细节亏损仍在。未获听评、长期或实际7.1.4验收；12通道候选只写FL/FR。</p>
<p><a href="启动后车内DNAV1.html">不含新增低频的同录音DNA研究</a> · <a href="状态素材与系统回放V1.html">其他状态素材</a></p>
<script>document.querySelectorAll('audio').forEach(a=>a.addEventListener('play',()=>document.querySelectorAll('audio').forEach(b=>{if(a!==b)b.pause()})))</script></html>'''
    page=a.workspace/'research/接火低频建立V1.html';assert not page.exists();page.write_text(body,encoding='utf-8',newline='\n');shutil.copy2(page,a.out/'page.html')
    url='http://127.0.0.1:8789/research/'+quote(page.name)
    with urlopen(url,timeout=15) as response:assert response.read()==page.read_bytes()
    for relative in re.findall(r'<audio[^>]*src="([^"]+)"',body):
        with urlopen(urljoin(url,relative),timeout=15) as response:assert response.read()==(a.out/'audio'/Path(relative).name).read_bytes()
    r.update(result='pass',page=url,page_sha256=sha(page),HTTP_bytes_verified=True,common_gain=.5,per_clip_gain_matching=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],page=r.get('page'),clips=len(r['clips']))))
