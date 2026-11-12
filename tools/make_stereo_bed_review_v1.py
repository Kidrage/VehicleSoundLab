"""Publish equal-gain old/new routing examples using the same current C sources."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import quote,urljoin
from urllib.request import urlopen

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
p.add_argument('--ffmpeg',type=Path,required=True);args=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha

args.out.mkdir(parents=True,exist_ok=False)
shutil.copy2(__file__,args.out/Path(__file__).name)
root=args.workspace/'references/analysis/stereo_bed_v1';verification=root/'verification1'
v=json.loads((verification/'report.json').read_text(encoding='utf-8'));assert v['result']=='technical_pass_only'
probe=verification/'bin/VslAtlasDrive_probe.exe';assert sha(probe)==v['binary_sha256'][probe.name]
models=[repo/'voices/cabin_anchors_v1'/f'E Cabin {name}.model' for name in ['Lower','Upper']]
options=[]
for model in models:options+=['--residual-anchor',str(repo/'voices/residual_atlas_v1'/(model.stem+'.residual'))]
prefix=args.out/'old_only'
command=[probe,*models,prefix,'--seconds','4','--scenario','fixed','--rpm','7600','--load','.8',
         '--stereo-bed','0','--spatial','1','--channels','2','--body-mix','.6','--residual-gain','.35','--gain','.25','--room','.2',*options]
result=subprocess.run([str(x) for x in command],cwd=repo,capture_output=True,timeout=60)
(args.out/'render.log').write_bytes(result.stdout+result.stderr);assert result.returncode==0
new_prefix=verification/'renders/E_bed_only_2'
for suffix in ['dna_raw','dna','dry','residual_raw','residual','harmonic_body_raw','harmonic_body','event_layer','auxiliary']:
    assert prefix.with_name(prefix.name+'_'+suffix+'.wav').read_bytes()==new_prefix.with_name(new_prefix.name+'_'+suffix+'.wav').read_bytes()
assert prefix.with_name(prefix.name+'_trace.csv').read_bytes()==new_prefix.with_name(new_prefix.name+'_trace.csv').read_bytes()
r=dict(schema='vsl.stereo-bed-review/1',result='running',command=[str(x) for x in command],clips=[],human_accepted=False,
       source_sha256={Path(__file__).relative_to(repo).as_posix():sha(__file__)},
       input_sha256={str(verification/'report.json'):sha(verification/'report.json'),str(probe):sha(probe)},browser_interaction_checked=False)
try:
    for key,path in [('objects',args.out/'old_only_render.wav'),('bed',verification/'renders/E_bed_only_2_render.wav')]:
        r['input_sha256'][str(path)]=sha(path)
        x,rate=sf.read(path,always_2d=True);assert rate==48000 and np.isfinite(x).all()
        steady=x[48000:];mid=.5*(steady[:,0]+steady[:,1]);side=.5*(steady[:,0]-steady[:,1])
        fade=np.ones(len(x));fade[:240]=np.linspace(0,1,240);fade[-240:]=np.linspace(1,0,240)
        y=x*fade[:,None];assert abs(y).max()<.95
        target=args.out/(key+'.wav');sf.write(target,y,48000,subtype='PCM_24')
        result=subprocess.run([str(args.ffmpeg),'-v','error','-i',str(target),'-f','null','-'],capture_output=True,timeout=30);assert result.returncode==0
        r['clips'].append(dict(key=key,frames=len(y),peak=float(abs(y).max()),sha256=sha(target),
            side_mid_dB=float(10*np.log10(np.mean(side*side)/np.mean(mid*mid))),FFmpeg_decodes=True))
    page=args.workspace/'research/立体声声床路由V1.html';assert not page.exists()
    body='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>立体声声床路由 V1</title><style>body{font:16px/1.65 system-ui;max-width:800px;margin:30px auto;padding:0 18px;background:#f4f5f5;color:#20272b}h1{font-size:25px}.card{background:white;padding:16px;margin:16px 0;border:1px solid #dce1e3;border-radius:8px}audio{width:100%;height:42px}.note{color:#52616b;font-size:14px}</style><h1>保留立体声的驾驶声源路由</h1><p>先暂停其他发声窗口。两版使用相同的 E 车内实验 DNA、低频分层和持续细节，相同控制和输出增益；区别在于如何进入空间输出。</p><p class="note">这是系统路由检查，尚无新音色听评认可。旧路径还包含对象滤波／房间响应，因此听感差异不只来自宽度。新路径保留已有左右差异，没有从近单声道的录音里创造新声场。</p>'''
    for key,title in [('objects','旧路径 · 中声道观察投到对象'),('bed','新路径 · 保留 L/R 声床')]:
        body+='<div class="card"><strong>'+title+'</strong><audio controls preload="metadata" src="../references/analysis/stereo_bed_v1/'+args.out.name+'/'+key+'.wav"></audio></div>'
    body+='''<p class="note">stereo 声床进入7.1.4时只占前左／前右；其余声道由单独的对象与已有反射负责。这里未开辅助／瞬态，所以高度、环绕与LFE保持静音。没有做响度匹配、压缩或额外增亮。</p><p>本地入口：Launch-Stereo-Bed.cmd。开始监听、点火后，勾选“空间声像”使用新声床路径；宽度100%保留模型左右差异，房间量作用于对象。默认停止发声。</p><script>document.querySelectorAll('audio').forEach(a=>a.addEventListener('play',()=>document.querySelectorAll('audio').forEach(b=>{if(a!==b)b.pause()})))</script></html>'''
    page.write_text(body,encoding='utf-8',newline='\n');shutil.copy2(page,args.out/'page.html')
    url=quote('http://127.0.0.1:8789/research/'+page.name,safe=':/')
    with urlopen(url,timeout=15) as response:assert response.status==200 and response.read()==page.read_bytes()
    for clip in r['clips']:
        relative='../references/analysis/stereo_bed_v1/'+args.out.name+'/'+clip['key']+'.wav'
        with urlopen(urljoin(url,relative),timeout=15) as response:assert response.status==200 and response.read()==(args.out/(clip['key']+'.wav')).read_bytes()
    r.update(result='pass',page=url,HTTP_bytes_verified=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],clips=r['clips'],page=r.get('page'))))
