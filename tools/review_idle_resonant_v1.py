"""Publish same-gain raw/C/detail auditions without replacing moving references."""
import argparse,json,shutil,subprocess,sys,urllib.request
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--render',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from drive_evidence_v1.sources import sha
from listening_v1.page import make_page

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',clips=[],source_sha256={},manual_browser_interaction=False)
try:
    report=json.loads((a.render/'report.json').read_text(encoding='utf-8'))
    assert report['result']=='render_technical_pass'
    r['render_report_sha256']=sha(a.render/'report.json')
    for path in [Path(__file__),repo/'tools/listening_v1/page.py']:
        r['source_sha256'][path.relative_to(repo).as_posix()]=sha(path)
        target=a.out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    signals={};manifest={};raw=a.render/'raw'
    for name,file in [('reference','reference.wav'),('original','original.wav'),
                     ('detail','add_only_8121907_mix.wav'),('replace35','replace35_8121907_mix.wav')]:
        x,rate=sf.read(raw/file,always_2d=True);assert rate==48000 and np.isfinite(x).all()
        signals[name]=x;manifest[name]={}
    bands={'whole':None,'body':[30,300],'texture':[400,1200],'edge':[1200,2800],'fine':[3000,8000]}
    for name,x in signals.items():
        for band,limits in bands.items():
            y=x
            if limits:
                taps=signal.firwin(2049,limits,pass_zero=False,fs=48000)
                y=signal.fftconvolve(x,taps[:,None],mode='same',axes=0)
            for duration in ('short','long'):
                if name=='reference' and duration=='long':continue
                count=len(signals['reference']) if duration=='short' else 288000
                offset=0 if name=='reference' else 96000
                clip=y[offset:offset+count].copy()*.5;assert len(clip)==count
                n=2048 if duration=='short' else 1024
                fade=np.sin(np.linspace(0,np.pi/2,n))**2
                clip[:n]*=fade[:,None];clip[-n:]*=fade[::-1,None]
                path=a.out/f'{name}_{band}_{duration}.wav'
                assert abs(clip).max()<.95;sf.write(path,clip,48000,subtype='PCM_24')
                url='http://127.0.0.1:8789/'+path.relative_to(a.workspace).as_posix()
                with urllib.request.urlopen(url,timeout=10) as response:assert response.read()==path.read_bytes()
                done=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-f','null','-'],capture_output=True,timeout=30)
                assert done.returncode==0
                manifest[name][band+'_'+duration]=path.name
                r['clips'].append(dict(file=path.name,frames=count,sha256=sha(path),HTTP_decode_pass=True))
    versions=dict(reference='录音参考 · 驻车低转',original='原 C DNA',detail='补入连续细节',replace35='补细节＋轻量谐波替换')
    labels=dict(whole='完整声音',body='30–300 Hz',texture='400–1200 Hz',edge='1.2–2.8 kHz',fine='3–8 kHz')
    page=make_page('驻车低转 · 细节对照',
        '先听录音与原C DNA，再比较两条细节候选。重点判断是否更像机械发动机，还是只增加了沙声、风声。',
        ['素材A的243.9–247.1秒，驻车尾部机位；准确RPM与冷热状态未确认。此处先研究低转声源，不代表热怠速已标定。',
         '统一0.5源增益 · 无逐条响度补偿或房间处理 · 只有一个播放器。录音只作短参考，不循环。',
         '保留原DNA低频主体；新增细节按这段素材重新拟合，持续生成新激励。本轮没有合格的弱周期能量包络，未加入周期颤动。',
         '这是离线候选，尚未接实时驾驶。此前行驶35%参考保持。'],
        versions,labels,dict(short='短对照 · 3.2秒',long='持续生成 · 6秒'),manifest,'reference')
    (a.out/'index.html').write_text(page,encoding='utf-8',newline='\n')
    js=page.split('<script>',1)[1].split('</script>',1)[0]
    (a.out/'player.js').write_text(js,encoding='utf-8',newline='\n')
    done=subprocess.run(['node','--check',str(a.out/'player.js')],capture_output=True,timeout=15)
    (a.out/'javascript_syntax.log').write_bytes(done.stdout+done.stderr);assert done.returncode==0
    assert page.count('<audio ')==1 and len(r['clips'])==35
    url='http://127.0.0.1:8789/'+(a.out/'index.html').relative_to(a.workspace).as_posix()
    with urllib.request.urlopen(url,timeout=10) as response:assert response.read()==(a.out/'index.html').read_bytes()
    r.update(result='review_technical_pass',url=url,page_sha256=sha(a.out/'index.html'),
        file_map=manifest,javascript_syntax_pass=True,one_player=True,common_gain=.5,per_file_gain=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],clips=len(r['clips']),url=r.get('url'))))
