"""Publish native-source audition without per-version loudness compensation."""
import argparse,html,json,shutil,subprocess,sys,urllib.request
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
a.out.mkdir(parents=True,exist_ok=False)
proof=a.workspace/'references/analysis/phase_texture_c_v1/verification1'
assert json.loads((proof/'report.json').read_text(encoding='utf-8'))['result']=='pass'
old=a.workspace/'baselines/phase_texture_v1/evidence/trial2';clips=[]
def verify(file,label):
    x,rate=sf.read(file,always_2d=True);assert rate==48000 and np.isfinite(x).all() and np.max(abs(x))<.95
    url='http://127.0.0.1:8789/'+file.relative_to(a.workspace).as_posix()
    with urllib.request.urlopen(url,timeout=10) as response:assert response.read()==file.read_bytes()
    done=subprocess.run(['ffmpeg','-v','error','-i',str(file),'-f','null','-'],capture_output=True,timeout=30)
    assert done.returncode==0
    clips.append(dict(file=file.name,label=label,sha256=sha(file),http_decode=True,url=url))
for name,label in [('accepted_original','原版：DNA＋相干低频'),('common_phase_0.5','已认可：离线轻量共同微扰')]:
    file=a.out/(name+'.wav');shutil.copy2(old/file.name,file);verify(file,label)
for source,name,label in [
    ('seed_8121907_amount_1','native_light','C持续生成：轻量共同微扰，1.00×'),
    ('pitch_0.9_amount_1','native_090','C持续生成：0.90×'),
    ('pitch_1.1_amount_1','native_110','C持续生成：1.10×')]:
    x,rate=sf.read(proof/source/'mix.wav',always_2d=True);assert rate==48000
    x=x[24000:384000].copy();n=240;fade=np.sin(np.linspace(0,np.pi/2,n))**2
    x[:n]*=fade[:,None];x[-n:]*=fade[::-1,None]
    file=a.out/(name+'.wav');sf.write(file,x,rate,subtype='PCM_24');verify(file,label)
page=['<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width">',
      '<title>共同微扰 C 监听</title><style>body{font:16px system-ui;max-width:800px;margin:36px auto;padding:0 20px;background:#f6f7f8}section{background:#fff;padding:20px;margin:16px 0;border-radius:12px}audio{width:100%}p{line-height:1.7}</style>',
      '<h1>共同微扰 · C 持续生成</h1><p>你已认可“离线轻量”更接近机械声。本页核对实时C移植是否保住这条声线。没有独立高频云、额外噪声或增亮；所有版本统一0.5增益，无逐条响度匹配。</p>',
      '<p>C沿用20–70Hz随机控制、自然样条和2微秒设计尺度／4微秒上界；随机数发生器换为独立C序列，因此不是冻结试听的逐样本复制。原幅度流、低频层保留。先比较已认可离线与C默认，随后才听有限变调。</p>',
      '<p>本地入口：Launch-Shared-Phase.cmd。默认停止，勾选“共同微扰 · 轻量”；可取消勾选回查原版。该入口为固定声学情境，尚未把此参数映射到完整驾驶状态。</p>']
for row in clips:page.append(f'<section><p>{html.escape(row["label"])}</p><audio controls preload="none" src="{row["file"]}"></audio></section>')
page.append('<script>document.addEventListener("play",e=>{if(e.target.tagName==="AUDIO")document.querySelectorAll("audio").forEach(a=>{if(a!==e.target)a.pause()})},true)</script></html>')
(a.out/'index.html').write_text('\n'.join(page),encoding='utf-8',newline='\n')
r=dict(result='five_native_review_clips_HTTP_decode_pass',clips=clips,page_sha256=sha(a.out/'index.html'),
       common_output_gain=.5,per_clip_loudness_normalization=False,native_listening_accepted=False)
(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],url='http://127.0.0.1:8789/'+(a.out/'index.html').relative_to(a.workspace).as_posix())))
