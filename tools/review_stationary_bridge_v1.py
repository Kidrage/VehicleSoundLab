"""Publish actual C audio, both four/five-anchor traces, and source references."""
import argparse,csv,json,os,shutil,sys,urllib.request
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','fit','drive','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
import soundfile as sf
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',clips=[],inputs={});scenes=[];traces={}
old_root=a.workspace/'baselines/stationary_recipe_v1'
old_digests={v['path']:v['sha256'] for v in load(old_root/'manifest.json')['files']}
def consume(path):
    r['inputs'][str(path)]=sha(path)
    if path.is_relative_to(old_root):assert r['inputs'][str(path)]==old_digests[path.relative_to(old_root).as_posix()]
    return path
def clip(scene,key,title,path,note,trace=None):
    wave,rate=sf.read(consume(path),always_2d=True);assert rate==48000 and wave.shape[1]==2
    wave*=.5;fade=np.sin(np.linspace(0,np.pi/2,240))**2;wave[:240]*=fade[:,None];wave[-240:]*=fade[::-1,None]
    dest=a.out/(scene['key']+'_'+key+'.wav');sf.write(dest,wave,48000,subtype='PCM_24')
    actual,_=sf.read(dest,always_2d=True);assert abs(actual).max()<.95 and np.max(abs(actual-wave))<=2**-23
    url='http://127.0.0.1:8789/'+dest.relative_to(a.workspace).as_posix()
    with urllib.request.urlopen(url,timeout=20) as response:assert response.read()==dest.read_bytes()
    row=dict(key=key,title=title,file=dest.name,frames=len(wave),note=note,trace=trace,sha256=sha(dest))
    scene['variants'].append(row);r['clips'].append(dict(scene=scene['key'],**row))
try:
    fit=load(consume(a.fit/'report.json'));drive=load(consume(a.drive/'report.json'));audit=load(consume(a.audit/'report.json'))
    assert fit['result']=='qualified_bridge_voices_rendered' and drive['result']==audit['result']=='passed'
    assert len(fit['anchors'])==1 and len(fit['rejected'])==2
    template=repo/'tools/stationary_bridge_v1/review.html'
    shutil.copy2(__file__,a.out/'executed_review.py');shutil.copy2(template,a.out/'executed_review.html')
    anchor=fit['anchors'][0];folder=a.fit/anchor['name']
    fixed=dict(key='fixed',title='新增中间声线 · 固定音高',info=f"声学根频率 {anchor['root_hz']:.3f} Hz · 未标定实车RPM",variants=[])
    note='持续合成8秒，未循环录音；固定声线的自然度仍待判断。'
    clip(fixed,'original','新增档 · 原DNA',folder/'original.wav',note)
    clip(fixed,'reference','素材 · 变速还原参考',folder/'reference.wav','源短窗经已有时钟归一再还原音高；不循环。')
    clip(fixed,'raw','素材 · 未处理源短窗',folder/'raw_source.wav','原始降转短窗，只作素材核对；同样施加全页共同增益与边缘淡化。')
    for seed in [8121907,23117,61927]:
        clip(fixed,f'candidate_{seed}',f'新增档 · DNA＋共振35% · 生成组{seed}',folder/f'candidate_{seed}.wav',note)
        clip(fixed,f'detail_{seed}',f'只听新增档细节 · 生成组{seed}',folder/f'detail_{seed}.wav','连续共振细节独奏，完整声线请切回混音。')
    scenes.append(fixed)
    old=a.workspace/'baselines/stationary_recipe_v1/evidence/drive2'
    support=[]
    for name,title in [('neutral','同一C驾驶器 · 空挡两次补油'),('shifts','同一C驾驶器 · 加速／换挡／制动')]:
        scene=dict(key=name,title=title,info='',variants=[])
        full_tables=[]
        for label,folder0,variant in [('four_dna',old,0),('four_detail',old,2),('five_dna',a.drive,0),('five_detail',a.drive,2)]:
            prefix=folder0/f'{name}_{variant}_2_240';trace_key=name+'_'+label
            with consume(prefix.with_suffix('.csv')).open(encoding='utf-8') as stream:rows=list(csv.DictReader(stream))
            full_tables.append([{k:v for k,v in row.items() if k!='detail_support'} for row in rows])
            traces[trace_key]=[{k:int(v) if k in ['gear','lifecycle','operating'] else float(v) for k,v in row.items() if k in ['rpm','gear','lifecycle','operating','detail_support']} for row in rows]
            title0={'four_dna':'原方案 · DNA','four_detail':'原方案 · DNA＋共振35%','five_dna':'新增中间声线 · DNA','five_detail':'新增中间声线 · DNA＋共振35%'}[label]
            clip(scene,label,title0,prefix.with_suffix('.wav'),'工程驾驶场景；相同踏板与挡位输入，RPM由模型计算。',trace_key)
            if label=='five_detail':clip(scene,'detail','新增中间声线 · 只听共振细节',prefix.with_name(prefix.name+'_detail.wav'),'共振细节独奏；支持量表示局部工程门控。',trace_key)
        scenes.append(scene)
        assert all(rows==full_tables[0] for rows in full_tables),'Different actual driver trajectories'
        four=np.array([v['detail_support'] for v in traces[name+'_four_detail']]);five=np.array([v['detail_support'] for v in traces[name+'_five_detail']])
        support.append(dict(scene=name,four_nonzero_trace_frames=int(np.count_nonzero(four)),five_nonzero_trace_frames=int(np.count_nonzero(five)),total_trace_frames=len(five),note='200Hz sampled geometric support, including muted lifecycle frames; not audible/measured coverage'))
    for i,row in enumerate(fit['rejected'],1):
        scene=dict(key='rejected'+str(i),title='未采用源窗 · '+row['name'],info=f"声学根频率 {row['root_hz']:.3f} Hz · 未发布模型",variants=[])
        folder0=a.fit/row['name']
        clip(scene,'raw','素材 · 未处理源短窗',folder0/'raw_source.wav','未采用窗：独立谱线一致性不足；尚未确定是否由录音叠加／声线变化或提取误差造成。')
        clip(scene,'reference','素材 · 变速还原参考',folder0/'reference.wav','处理后的短参考；这不是已通过的生成候选。')
        scenes.append(scene)
    fig,axes=plt.subplots(2,1,figsize=(10,7),layout='constrained')
    folder=a.fit/anchor['name']
    for label,file in [('Source','reference.wav'),('Original DNA','original.wav'),('Resonant35','candidate_8121907.wav')]:
        wave,_=sf.read(folder/file,always_2d=True)
        if label!='Source':wave=wave[24000:]
        hz,power=signal.welch(wave[:,0],fs=48000,nperseg=2048,noverlap=1536,detrend=False)
        axes[0].plot(hz,10*np.log10(power+1e-30),label=label,lw=.8)
    axes[0].set(xscale='log',xlim=(100,14000),ylim=(-130,-20),xlabel='Hz',ylabel='PSD dBFS/Hz',title='New middle observation | left | no level matching')
    roots_old=np.array([31.52219356431996,47.39127187830898,60.83004535315176]);roots_new=np.sort(np.r_[roots_old,anchor['root_hz']])
    for y,roots,label in [(0,roots_old,'Previous 3 detail anchors'),(1,roots_new,'One additional qualified anchor')]:
        for root in roots:axes[1].plot([root*.9,root*1.1],[y,y],lw=8,solid_capstyle='butt',alpha=.7)
        axes[1].plot(roots,np.full_like(roots,y),'ko',ms=3)
    axes[1].set(yticks=[0,1],yticklabels=['Previous','Candidate'],xlabel='Acoustic root Hz, not measured RPM',ylim=(-.5,1.5),title='Geometric local support | gaps remain')
    axes[0].legend(fontsize=8)
    for ax in axes:ax.grid(alpha=.2)
    fig.savefig(a.out/'spectrum_support.png',dpi=130);plt.close(fig)
    data=dict(scenes=scenes,traces=traces);save(a.out/'data.json',data)
    page=template.read_text('utf-8').replace('__DATA__',json.dumps(data,ensure_ascii=False,separators=(',',':')))
    assert page.count('<audio ')==1 and '__DATA__' not in page
    (a.out/'index.html').write_text(page,encoding='utf-8',newline='\n')
    (a.out/'player.js').write_text(page.split('<script>')[1].split('</script>')[0],encoding='utf-8',newline='\n')
    url='http://127.0.0.1:8789/'+(a.out/'index.html').relative_to(a.workspace).as_posix()
    with urllib.request.urlopen(url,timeout=20) as response:assert response.read()==(a.out/'index.html').read_bytes()
    r.update(result='passed',url=url,clip_count=len(r['clips']),support_samples=support,common_gain=.5,
             all_scenes_same_driver=True,geometric_support_complete=False,human_accepted=False,native_default_changed=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
