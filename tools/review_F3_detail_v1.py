"""Publish one-player unchanged-DNA versus source-specific additive-detail comparisons."""
import argparse
from pathlib import Path
import shutil
import sys
import urllib.request
from research_archive_v1 import load,save,sha
p=argparse.ArgumentParser(description=__doc__)
for key in ('workspace','out'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
a.out.mkdir(parents=True,exist_ok=False);root=a.workspace/'references/analysis/F3_detail_v1'
r=dict(result='running',clips=[],sources={},gain=.5,fade_frames=240)
try:
    assert load(root/'audit1/report.json')['result']=='passed'
    fit=load(root/'fit1/report.json');source=a.workspace/'baselines/F3_lift_voice_v1/evidence/fit2/F3 Sixth Before Upshift'
    items=[('main',source/'DNA_1.wav','仅主声线 · 8秒','沿用上轮主声线，原细节序列1。'),
        ('seed1',root/'fit1/candidate_8121907.wav','主声线＋细节 · 生成1','主声线保持不变；新增细节序列1。'),
        ('seed23117',root/'fit1/candidate_23117.wav','主声线＋细节 · 生成2','主声线保持不变；新增细节序列2。'),
        ('seed61927',root/'fit1/candidate_61927.wav','主声线＋细节 · 生成3','主声线保持不变；新增细节序列3。'),
        ('detail',root/'fit1/detail_8121907.wav','只听新增细节 · 8秒','同一层的独立持续声；实际混音增益。'),
        ('reference',source/'reference.wav','固定音高原声参考 · 短片段','同一局部素材的固定音高参考，保留双声道。'),
        ('original',source/'native.wav','升挡前原声 · 0.9秒','F3原音频199.6–200.5秒，保留原有升速。')]
    for key,path,title,note in items:
        x,rate=sf.read(path,always_2d=True);assert rate==48000 and x.shape[1]==2
        y=x*.5;fade=.5-.5*np.cos(np.pi*np.arange(240)/240);y[:240]*=fade[:,None];y[-240:]*=fade[::-1,None]
        assert abs(y).max()<.95
        dest=a.out/(key+'.wav');sf.write(dest,y,48000,subtype='FLOAT')
        actual,rate=sf.read(dest,always_2d=True);assert np.array_equal(actual,y.astype('float32').astype('float64'))
        r['clips'].append(dict(key=key,file=dest.name,title=title,note=note,frames=len(actual),source_sha256=sha(path),sha256=sha(dest)))
    shutil.copy2(root/'audit1/diagnostic.png',a.out/'diagnostic.png');save(a.out/'data.json',dict(clips=r['clips']))
    template=repo/'tools/F3_detail_v1/review.html'
    (a.out/'index.html').write_text(template.read_text(encoding='utf-8').replace('__DATA__',(a.out/'data.json').read_text(encoding='utf-8')),encoding='utf-8',newline='\n')
    for name in ('tools/review_F3_detail_v1.py','tools/F3_detail_v1/review.html'):
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    r['url']='http://127.0.0.1:8789/'+a.out.relative_to(a.workspace).as_posix()+'/index.html'
    for name in ['index.html','data.json','diagnostic.png']+[v['file'] for v in r['clips']]:
        with urllib.request.urlopen(r['url'].rsplit('/',1)[0]+'/'+name,timeout=10) as response:assert response.read()==(a.out/name).read_bytes()
    r.update(result='seven_additive_detail_clips_ready',same_DNA=True,withdrawal=0,room=False,runtime_changed=False,human_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print({key:r.get(key) for key in ('result','url')})
