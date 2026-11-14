"""Publish raw-reference/main-line comparisons, with common gain and no state promotion."""
import argparse
import os
from pathlib import Path
import shutil
import sys
import urllib.request
from research_archive_v1 import load,save,sha

p=argparse.ArgumentParser(description=__doc__)
for name in ('workspace','out'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
a.out.mkdir(parents=True,exist_ok=False)
root=a.workspace/'references/analysis/F3_lift_voice_v1'
r=dict(result='running',clips=[],sources={},gain=.5,fade_frames=240,room=False,human_accepted=False)
try:
    assert load(root/'audit3/report.json')['result']=='passed'
    fit=load(root/'fit2/report.json');folder=root/'fit2/F3 Sixth Before Upshift'
    items=[('original',folder/'native.wav','六挡升挡前原声 · 0.9秒','F3原音频199.6–200.5秒，保留原有升速。'),
        ('reference',folder/'reference.wav','固定音高参考 · 短片段','同一局部素材的固定音高参考，保留双声道。')]
    items += [(f'seed{seed}',folder/f'DNA_{seed}.wav',f'持续主声线 · 生成{i+1}',f'持续生成8秒，细节序列{seed}。') for i,seed in enumerate((1,23117,61927))]
    items += [('slowing',root/'fit2/F3 Seventh Slowing/native.wav','七挡减速原声 · 1秒','F3原音频201.3–202.3秒。当前仅保留原声。'),
        ('after',root/'fit2/F3 Near Sixth After Downshift/native.wav','降挡后原声 · 1秒','F3原音频203.3–204.3秒，后半段仪表叠图消失。')]
    for key,source,title,note in items:
        x,rate=sf.read(source,always_2d=True);assert rate==48000 and x.shape[1]==2
        y=x*.5;fade=.5-.5*np.cos(np.pi*np.arange(240)/240)
        y[:240]*=fade[:,None];y[-240:]*=fade[::-1,None]
        assert np.isfinite(y).all() and abs(y).max()<.95
        path=a.out/(key+'.wav');sf.write(path,y,48000,subtype='FLOAT')
        saved,rate=sf.read(path,always_2d=True)
        assert np.array_equal(saved,y.astype('float32').astype('float64'))
        r['clips'].append(dict(key=key,file=path.name,title=title,note=note,frames=len(y),
            source_sha256=sha(source),sha256=sha(path),peak_FS=float(abs(saved).max())))
    # Compare training-band moments descriptively; no per-clip loudness correction.
    bands=((28,120),(120,400),(400,1200),(1200,3000),(3000,8000),(8000,14000))
    powers={}
    for key,source,_,_ in items:
        x,rate=sf.read(source,always_2d=True)
        hz,density=signal.welch(x,48000,nperseg=2048,noverlap=1024,axis=0)
        powers[key]=np.array([[np.sum(density[(hz>=lo)&(hz<hi),c])*48000/2048 for c in (0,1)] for lo,hi in bands])
    metrics=dict(bands_hz=bands,raw_LR_powers={key:value.tolist() for key,value in powers.items()},
        generated_vs_short_fixed_reference_db={key:(10*np.log10(np.maximum(powers[key],1e-30)/np.maximum(powers['reference'],1e-30))).tolist() for key in powers if key.startswith('seed')},
        scope='Descriptive training snapshot, not held-out realism or transient/state coverage. Spectral residual includes environmental/inharmonic sources, not a physical noise allocation.')
    save(a.out/'band_metrics.json',metrics)
    shutil.copy2(root/'audit3/diagnostic.png',a.out/'diagnostic.png')
    save(a.out/'data.json',dict(clips=r['clips']))
    template=repo/'tools/F3_lift_voice_v1/review.html'
    html=template.read_text(encoding='utf-8').replace('__DATA__',(a.out/'data.json').read_text(encoding='utf-8'))
    (a.out/'index.html').write_text(html,encoding='utf-8',newline='\n')
    for name in ('tools/review_F3_lift_voice_v1.py','tools/F3_lift_voice_v1/review.html'):
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    r['url']='http://127.0.0.1:8789/'+a.out.relative_to(a.workspace).as_posix()+'/index.html'
    for name in ['index.html','data.json','diagnostic.png']+[v['file'] for v in r['clips']]:
        with urllib.request.urlopen(r['url'].rsplit('/',1)[0]+'/'+name,timeout=10) as response:assert response.read()==(a.out/name).read_bytes()
    r.update(result='seven_reference_and_mainline_clips_ready',runtime_changed=False,physical_RPM_or_load=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print({k:r.get(k) for k in ('result','url')})
