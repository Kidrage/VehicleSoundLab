"""Native DSP020 listening renders and parity checks against frozen DSP019."""
import json,csv,subprocess
from runtime_review import ROOT,sha,rms
import numpy as np
import soundfile as sf
OUT=ROOT/'renders/v0.20.0'
BIN=ROOT/'build-v020/Release'
CASES={'low':('1200 RPM','fixed',5,1200,.4,(2.5,5)),
       'mid':('4000 RPM','fixed',5,4000,.85,(2.5,5)),
       'high':('8000 RPM','fixed',5,8000,.85,(2.5,5)),
       'neutral':('空挡补油与落转','neutral',8,850,.18,(1.6,8)),
       'lift':('断油与恢复（验证）','lift',7.5,5000,.85,None)}
VARIANTS={'original':0,'steady':1,'varying':2}
def run(args,ok=True):
    r=subprocess.run(list(map(str,args)),cwd=ROOT,capture_output=True,text=True,timeout=120)
    if ok and r.returncode:raise RuntimeError(r.stderr+r.stdout)
    return dict(returncode=r.returncode,stdout=r.stdout.strip(),stderr=r.stderr.strip())
def rows(path):
    with path.open(encoding='utf-8') as f:return list(csv.DictReader(f))
def main():
    if OUT.exists():raise SystemExit('Preserve completed/partial DSP020 render attempt.')
    OUT.mkdir();result=dict(dsp='0.20.0',seed=48271,cases={},subjectively_accepted=False);page={}
    for name,(label,scenario,seconds,rpm,load,crop) in CASES.items():
        folder=OUT/name;folder.mkdir();arrays={};versions={};traces={}
        for tag,mode in VARIANTS.items():
            take=folder/f'{tag}.vsltake';prefix=folder/tag
            run([BIN/'vsl_character_probe.exe',take,scenario,seconds,rpm,load,0,0,0,0,mode,1])
            rendered=run([BIN/'vsl_take_render.exe',take,folder/f'{tag}.wav','--stems',prefix])
            x,sr=sf.read(folder/f'{tag}.wav',always_2d=True);assert sr==48000 and np.isfinite(x).all() and abs(x).max()<.95
            arrays[tag]=x;traces[tag]=rows(folder/f'{tag}.vsltake.csv')
            assert int(traces[tag][-1]['pulse_overflow'])==0
            versions[tag]=dict(wav_sha256=sha(folder/f'{tag}.wav'),take_sha256=sha(take),rms_dbfs=rms(x),peak=float(abs(x).max()),render=rendered)
        keys=[k for k in traces['original'][0] if k not in ['firing_source_target','pulse_amount_target','pulse_mix','pulse_variation'] and not k.startswith('pulse_')]
        for tag in ['steady','varying']:
            assert [[r[k] for k in keys] for r in traces[tag]]==[[r[k] for k in keys] for r in traces['original']]
            for path in folder.glob('original_*.wav'):
                suffix=path.name.removeprefix('original_')
                if suffix not in ['exhaust_left.wav','exhaust_right.wav','body.wav']:
                    assert path.read_bytes()==(folder/f'{tag}_{suffix}').read_bytes(),suffix
        comparison={}
        old=ROOT/'renders/firing_pulse_v1'/name
        if old.exists():
            assert (folder/'original.wav').read_bytes()==(old/'native.wav').read_bytes(),name
            comparison['OSC_matches_frozen019_float_WAV']=True
            for tag in ['steady','varying']:
                y,_=sf.read(old/f'{tag}.wav',always_2d=True);start=round(1.6*48000)
                error=float(abs(arrays[tag][start:]-y[start:]).max());assert error<2e-7,(name,tag,error)
                comparison[tag+'_settled_max_abs_vs_offline_candidate']=error
        audition={}
        if crop:
            trimmed={tag:x[round(crop[0]*48000):round(crop[1]*48000)].copy() for tag,x in arrays.items()}
            ramp=.5-.5*np.cos(np.linspace(0,np.pi,240))
            for x in trimmed.values():x[:240]*=ramp[:,None];x[-240:]*=ramp[::-1,None]
            gains={tag:10**((-23-rms(x))/20) for tag,x in trimmed.items()}
            trim=min(1,.85/max(float(abs(x).max())*gains[tag] for tag,x in trimmed.items()))
            for tag,x in trimmed.items():
                gain=gains[tag]*trim;path=folder/f'audition_{tag}.wav';sf.write(path,x*gain,48000,subtype='PCM_24')
                check,_=sf.read(path,always_2d=True);assert abs(check-x*gain).max()<1.3e-7
                audition[tag]=dict(file=path.name,sha256=sha(path),gain_db=float(20*np.log10(gain)),crop_seconds=crop,rms_dbfs=rms(check),endpoint_fade_ms=5)
            page[name]=dict(label=label,takes={tag:f'../renders/v0.20.0/{name}/'+r['file'] for tag,r in audition.items()},gains={tag:r['gain_db'] for tag,r in audition.items()})
        result['cases'][name]=dict(variants=versions,comparison=comparison,audition=audition,identical_original_drive_traces=True,seven_other_direct_sources_exact=True)
        print('Native listening/render parity:',name,comparison,flush=True)
    rejected=run([BIN/'vsl_take_render.exe',ROOT/'renders/app0.19.1/ui_take_smoke.vsltake',OUT/'should_not_exist.wav'],ok=False)
    assert rejected['returncode']==2 and not (OUT/'should_not_exist.wav').exists()
    result['old_take_rejected_without_translation']=rejected
    template=(ROOT/'tools/firing_pulse_page.html').read_text(encoding='utf-8')
    template=template.replace('FIRING SOURCE 1','NATIVE DSP 0.20.0').replace('<title>逐缸压力源','<title>V020 实时燃烧声源')
    template=template.replace('<h1>从每一次点火形成压力波</h1>','<h1>V020 · 实时燃烧声源</h1>')
    template=template.replace('当前 C 核心的同一驾驶输入、种子与点火顺序。','本页由原生 DSP 0.20.0 从同一驾驶输入生成，种子与点火顺序一致。实时程序的 Sound detail 底部可选择相同声源。')
    template=template.replace('中、高转只播放','恒转速场景只播放').replace('逐缸压力源实验V1.md','V020实时燃烧声源.md')
    template=template.replace('同一次点火的强度和持续时间差异。','同一次点火的强度和持续时间差异。两种事件源均为新候选，尚未确认减少电子感。')
    (ROOT/'research/V020燃烧声源试听.html').write_text(template.replace('__DATA__',json.dumps(page,ensure_ascii=False).replace('</','<\\/')),encoding='utf-8')
    result['page_data']=page;result['files']={p.relative_to(OUT).as_posix():sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
    (OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
