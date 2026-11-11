"""Build repeatable review WAVs, object stems, channel metadata and measured checks."""
from pathlib import Path
import sys,subprocess,json,hashlib,csv,struct
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
out=ROOT/'renders/v0.2.0';out.mkdir(exist_ok=True);(out/'stems').mkdir(exist_ok=True)
exe=ROOT/'build/Release/vsl_render.exe'
cases={
 'v10_drive_stereo':['--seconds','30','--width','.8','--trace',str(out/'v10_drive_trace.csv')],
 'v10_drive_mono':['--seconds','30','--width','0'],
 'v10_drive_cabin':['--seconds','30','--width','.8','--cabin'],
 'v10_drive_714':['--seconds','30','--channels','12','--stems',str(out/'stems/v10'),'--scene',str(out/'scene.json')],
 'v10_5000_light':['--seconds','6','--rpm','5000','--load','.12','--width','.8'],
 'v10_5000_loaded':['--seconds','6','--rpm','5000','--load','.85','--width','.8'],
 'v10_5000_overrun':['--seconds','6','--rpm','5000','--load','-.4','--width','.8'],
 'v10_idle_low_orders':['--seconds','6','--rpm','850','--load','.12','--detail','0'],
 'v10_idle_high_orders':['--seconds','6','--rpm','850','--load','.12','--detail','1'],
}
for i,name in [(1,'v8'),(2,'flat6'),(3,'scifi'),(4,'v12')]:cases[name+'_drive']=['--seconds','12','--profile',str(i)]
metadata_only='--metadata-only' in sys.argv
report=json.loads((out/'verification.json').read_text()) if metadata_only else dict(version='0.2.0',seed=48271,cases={})
for name,args in cases.items():
    if metadata_only and name!='v10_drive_714':continue
    path=out/f'{name}.wav';command=[str(exe),str(path),*args];subprocess.run(command,check=True,capture_output=True)
    x,sr=sf.read(path,always_2d=True);assert sr==48000 and np.isfinite(x).all()
    assert abs(x).max()<.95
    metrics=dict(command=command,sample_rate=sr,channels=x.shape[1],frames=len(x),
        peak_dbfs=float(20*np.log10(max(abs(x).max(),1e-15))),
        rms_dbfs=float(10*np.log10(max(np.mean(x*x),1e-30))),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    if x.shape[1]==2:
        valid=x[int(1.8*sr):-sr//4]
        mid=valid.mean(axis=1);side=(valid[:,0]-valid[:,1])*.5
        f,p=signal.welch(valid,sr,nperseg=8192,axis=0)
        metrics.update(side_to_mid_db=float(10*np.log10(max(np.mean(side*side),1e-30)/max(np.mean(mid*mid),1e-30))),
            high_3k_14k_fraction=float(p[(f>=3000)&(f<14000)].sum()/p.sum()))
    else:
        # Read actual extensible format rather than infer it from a file name.
        data=path.read_bytes()[:128];offset=data.index(b'fmt ')+8;fmt=data[offset:offset+40]
        code,ch,rate,byte_rate,align,bits=struct.unpack('<HHIIHH',fmt[:16])
        mask=struct.unpack('<I',fmt[20:24])[0];subformat=struct.unpack('<I',fmt[24:28])[0]
        assert (code,ch,mask,bits,subformat)==(65534,12,0x2d63f,32,3)
        metrics.update(speaker_mask=hex(mask),subformat='IEEE float32',channel_rms_dbfs=(10*np.log10(np.maximum(np.mean(x*x,axis=0),1e-30))).tolist())
    report['cases'][name]=metrics
    print(name,'peak',round(metrics['peak_dbfs'],1),'dBFS')
assert report['cases']['v10_drive_mono']['side_to_mid_db'] < -180
trace=list(csv.DictReader((out/'v10_drive_trace.csv').open()))
assert {'CRANK','CATCH','RUNNING'} <= {r['lifecycle'] for r in trace}
assert {'IDLE','PULL','OVERRUN','SHIFT CUT','SHIFT RECOVER'} <= {r['operating'] for r in trace}
assert int(trace[-1]['shifts'])>=3 and int(trace[-1]['overruns'])>=1
# Positive load changes high-band balance even with exactly the same target RPM.
assert report['cases']['v10_5000_loaded']['high_3k_14k_fraction']>report['cases']['v10_5000_light']['high_3k_14k_fraction']
# Synthesis masters retain state dynamics. Only mono/stereo comparison COPIES
# receive RMS matching for audition; the same shared peak trim applies to both.
pair={n:sf.read(out/f'v10_drive_{n}.wav',always_2d=True)[0] for n in ['mono','stereo']}
for name,x in pair.items():pair[name]=x*(10**(-23/20)/np.sqrt(np.mean(x*x)))
gain=min(1,.85/max(abs(x).max() for x in pair.values()))
for name,x in pair.items():sf.write(out/f'audition_drive_{name}_rms_matched.wav',x*gain,48000,subtype='PCM_24')
scene=json.loads((out/'scene.json').read_text(encoding='utf-8'))
assert scene['channels']==['FL','FR','FC','LFE','BL','BR','SL','SR','TFL','TFR','TBL','TBR']
for obj in scene['objects']:
    path=Path(obj['file']);data,sr=sf.read(path);assert data.ndim==1 and len(data)==30*48000 and np.isfinite(data).all()
    obj['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    obj['file']=str(path.relative_to(out)).replace('\\','/')
(out/'scene.json').write_text(json.dumps(scene,indent=2),encoding='utf-8')
report['trace_summary']=dict(lifecycle=sorted({r['lifecycle'] for r in trace}),operating=sorted({r['operating'] for r in trace}),
    shifts=int(trace[-1]['shifts']),overruns=int(trace[-1]['overruns']),event_hits=int(trace[-1]['hits']))
report['limits']='No subjective realism score. V10/V8/flat6/scifi/V12 are engineering templates. 7.1.4 verified as file/routing only, no speaker-array listening test.'
(out/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report['trace_summary']))
