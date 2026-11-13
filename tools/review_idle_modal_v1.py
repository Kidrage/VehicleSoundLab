"""A single-player source/old-DNA/new-idle comparison, with explicit gain."""
import argparse,json,shutil,subprocess,sys,urllib.request
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__); p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True); a=p.parse_args(); repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from drive_evidence_v1.sources import sha
from listening_v1.page import make_page

a.out.mkdir(parents=True,exist_ok=False); r=dict(result='running',clips=[],sources={})
try:
    parent=a.workspace/'references/analysis/idle_modal_v1/trial4'
    audited=a.workspace/'references/analysis/idle_modal_v1/audit2/report.json'
    assert json.loads(audited.read_text(encoding='utf-8'))['result'].startswith('native_sources_')
    r['audit_report_sha256']=sha(audited)
    root=850/120; schedule=a.out/'old_dna_native_hz.txt'
    schedule.write_text(f'0 {root:.17g}\n576000 {root:.17g}\n',encoding='ascii')
    exe=repo/'build-state-passage-v1/Release/state_passage_probe.exe'
    model=repo/'voices/dna_bank_v1/V10 Exterior.model'
    cmd=[str(v) for v in (exe,schedule,a.out/'old_DNA_source.wav',a.out/'old_DNA_trace.csv',1,149921,0,model)]
    done=subprocess.run(cmd,cwd=repo,capture_output=True,timeout=120)
    (a.out/'old_DNA_render.log').write_bytes(done.stdout+done.stderr); assert done.returncode==0
    r['old_DNA_baseline']=dict(command=cmd,exe_sha256=sha(exe),model_sha256=sha(model),root_hz=root,
        scope='Existing C atlas source only at constant engineering idle coordinate; no full driver/events/room')
    signals={}
    for name,path in [('reference',parent/'F2_holdout.wav'),('original',a.out/'old_DNA_source.wav'),
        ('modal',parent/'modal_only.wav'),('detail',parent/'mix_149921.wav')]:
        x,rate=sf.read(path,always_2d=True); assert rate==48000 and np.isfinite(x).all(); signals[name]=x
    # Old C DNA has unrelated output gain. One explicitly disclosed scalar
    # matches its 30..14k RMS to the TRAINING reference, before common gain.
    train,_=sf.read(parent/'F2_training.wav',always_2d=True)
    def band_rms(x):
        f,power=signal.welch(x,fs=48000,nperseg=24000,noverlap=0,detrend=False,axis=0)
        return np.sqrt(power[(f>=30)&(f<14000)].sum()*2/2)
    old_gain=float(band_rms(train)/band_rms(signals['original']))
    signals['original']*=old_gain
    r['old_DNA_RMS_match_gain']=old_gain
    common=min(1.,.85/max(abs(x).max() for x in signals.values()))
    bands=dict(whole=None,body=[30,400],mechanical=[400,2200],fine=[2200,14000])
    files={name:{} for name in signals}
    for name,x in signals.items():
        for band,limits in bands.items():
            y=x
            if limits:
                taps=signal.firwin(2049,limits,fs=48000,pass_zero=False)
                y=signal.fftconvolve(x,taps[:,None],mode='same',axes=0)
            for duration,count in [('short',144000),('long',576000)]:
                if name=='reference' and duration=='long': continue
                clip=y[:count].copy()*common; assert len(clip)==count
                ramp=np.sin(np.linspace(0,np.pi/2,1024))**2
                clip[:1024]*=ramp[:,None]; clip[-1024:]*=ramp[::-1,None]
                path=a.out/f'{name}_{band}_{duration}.wav'; sf.write(path,clip,48000,subtype='PCM_24')
                decoded,rate=sf.read(path,always_2d=True)
                assert rate==48000 and decoded.shape==clip.shape and abs(decoded-clip).max()<=2**-23
                with urllib.request.urlopen('http://127.0.0.1:8789/'+path.relative_to(a.workspace).as_posix(),timeout=10) as response:
                    assert response.read()==path.read_bytes()
                files[name][band+'_'+duration]=path.name
                r['clips'].append(dict(file=path.name,frames=count,sha256=sha(path)))
    page=make_page('怠速 · 从原生素材重做',
        '先比较原录音、旧行驶DNA降调、新怠速候选，再连续听12秒，留意嗡鸣、拍频和高频是否自然。',
        ['原声：F2 LP-610尾排9–12秒；新候选仅用6–9秒训练。旧DNA来自另一款Performante录音，车型、机位、实际RPM不同，不是严格同工况还原测试。',
         '新候选：13条实测独立声线＋同素材的连续共振细节；没有原片循环、额外房间或人为周期抖音。它是新方法试听原型，尚未替换C驾驶Demo，也未取得共同发动机时钟资格。',
         '旧C声源只做一次30Hz–14kHz RMS对齐；新候选、声线独奏和原声使用同一源增益。所有输出再乘相同保护增益，不逐条补偿高频或候选响度。',
         '短对照3秒；新声源持续生成12秒，录音不循环。独立频率可能产生拍频，请特别检查长听。'],
        dict(reference='原录音 · F2怠速（未参与拟合）',original='旧行驶DNA降调 · C声源',
            modal='新怠速 · 只听独立声线',detail='新怠速候选 · 声线＋共振细节'),
        dict(whole='完整声音',body='30–400 Hz',mechanical='400–2200 Hz',fine='2.2–14 kHz'),
        dict(short='短对照 · 3秒',long='连续生成 · 12秒'),files,'detail')
    (a.out/'index.html').write_text(page,encoding='utf-8')
    js=page.split('<script>',1)[1].split('</script>',1)[0]; (a.out/'player.js').write_text(js,encoding='utf-8')
    done=subprocess.run(['node','--check',str(a.out/'player.js')],capture_output=True,timeout=15)
    assert done.returncode==0 and page.count('<audio ')==1
    url='http://127.0.0.1:8789/'+(a.out/'index.html').relative_to(a.workspace).as_posix()
    with urllib.request.urlopen(url,timeout=10) as response: assert response.read()==(a.out/'index.html').read_bytes()
    for source in [Path(__file__),repo/'tools/listening_v1/page.py']:
        dest=a.out/'exact_sources'/source.relative_to(repo); dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,dest); r['sources'][source.relative_to(repo).as_posix()]=sha(source)
    r.update(result='single_player_review_decoded_and_HTTP_verified',url=url,one_player=True,
        common_gain=common,listening_accepted=False,page_sha256=sha(a.out/'index.html'),files=files)
except Exception as exc: r.update(result='failed',error=repr(exc)); raise
finally: (a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(result=r['result'],url=r.get('url'),clips=len(r['clips'])),ensure_ascii=False),flush=True)
