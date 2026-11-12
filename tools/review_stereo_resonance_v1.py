"""Create one dry, common-gain player for the separate startup-settling stereo candidate."""
import argparse,json,shutil,subprocess,sys,urllib.request
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for name in ('workspace','verification','fit','out'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from drive_evidence_v1.sources import sha
from listening_v1.page import make_page
a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',clips=[],sources={},inputs={},manual_browser_interaction=False)
try:
    v=json.loads((a.verification/'report.json').read_text(encoding='utf-8'))
    assert v['result']=='stereo_candidate_technical_pass'
    assert sha(a.fit/'report.json')==v['fit_report_sha256']
    for name,digest in v['evidence_sha256'].items():assert sha(a.verification/name)==digest,name
    for path in (Path(__file__),repo/'tools/listening_v1/page.py'):
        target=a.out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target);r['sources'][path.relative_to(repo).as_posix()]=sha(path)
    for path in (a.verification/'report.json',a.fit/'report.json',a.fit/'reference.wav'):
        r['inputs'][str(path)]=sha(path)
    dna,rate=sf.read(a.verification/'DNA_50s.wav',always_2d=True);assert rate==48000;dna=dna[96000:384000]
    detail=np.fromfile(a.verification/'detail_8121907.f64',dtype='<f8').reshape(-1,2)[:len(dna)]
    reference,rate=sf.read(a.fit/'reference.wav',always_2d=True);assert rate==48000
    signals=dict(original=dna,half=dna+.5*detail,full=dna+detail,detail=detail,reference=reference)
    bands=dict(whole=None,mid=[400,1200],high=[1200,8000]);files={}
    for name,x in signals.items():
        files[name]={}
        for band,limits in bands.items():
            y=x
            if limits:y=signal.fftconvolve(x,signal.firwin(2049,limits,pass_zero=False,fs=48000)[:,None],mode='same',axes=0)
            for duration in ('short','long'):
                if name=='reference' and duration=='long':continue
                count=len(reference) if duration=='short' else len(dna)
                clip=y[:count].copy()*.5
                fade=np.sin(np.linspace(0,np.pi/2,512))**2;clip[:512]*=fade[:,None];clip[-512:]*=fade[::-1,None]
                path=a.out/f'{name}_{band}_{duration}.wav';assert abs(clip).max()<.95
                sf.write(path,clip,48000,subtype='PCM_24');files[name][band+'_'+duration]=path.name
                url='http://127.0.0.1:8789/'+path.relative_to(a.workspace).as_posix()
                with urllib.request.urlopen(url,timeout=10) as response:assert response.read()==path.read_bytes()
                done=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-f','null','-'],capture_output=True,timeout=30)
                assert done.returncode==0
                r['clips'].append(dict(file=path.name,frames=count,sha256=sha(path),HTTP_decode_pass=True))
    page=make_page('启动后低转 · 双声道细节候选',
        '先听原DNA，再切换细节50%与100%。判断新增部分是机械纹理，还是风声、砂声；同时留意左右声道关系。',
        ['素材A的38.48–39.51秒，启动后的车内稳定段；不是已确认的热怠速，也不代表车外尾排。',
         '全部采用相同0.5源增益，无逐条响度补偿或新增房间处理。录音参考只有1.03秒，不循环。',
         '600–850 Hz仍有缺口；此候选先补其余频带和声道差异。长片段是连续新生成的声音。',
         '行驶35%配方保持；这个候选尚未接入驾驶状态。'],
        dict(original='原DNA',half='DNA＋细节50%',full='DNA＋细节100%',detail='只听新增细节',reference='原录音 · 短参考'),
        dict(whole='完整声音',mid='400–1200 Hz',high='1.2–8 kHz'),
        dict(short='短对照 · 1.03秒',long='持续生成 · 6秒'),files,'original')
    (a.out/'index.html').write_text(page,encoding='utf-8',newline='\n')
    (a.out/'player.js').write_text(page.split('<script>',1)[1].split('</script>',1)[0],encoding='utf-8')
    done=subprocess.run(['node','--check',str(a.out/'player.js')],capture_output=True,timeout=15)
    (a.out/'javascript_syntax.log').write_bytes(done.stdout+done.stderr);assert done.returncode==0
    assert len(r['clips'])==27 and page.count('<audio ')==1
    url='http://127.0.0.1:8789/'+(a.out/'index.html').relative_to(a.workspace).as_posix()
    with urllib.request.urlopen(url,timeout=10) as response:assert response.read()==(a.out/'index.html').read_bytes()
    r.update(result='review_technical_pass',url=url,one_player=True,common_gain=.5,per_file_gain=False,
        page_sha256=sha(a.out/'index.html'),javascript_syntax_pass=True,listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(result=r['result'],clips=len(r['clips']),url=r.get('url'))))
