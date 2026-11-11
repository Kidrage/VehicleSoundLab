"""V0.6 common-pin geometry: identical driver traces, phase-dependent sound."""
from pathlib import Path
import json
import subprocess
import sys
from runtime_review import ROOT,render,audition,sha,smoke,scene_paths,rms
import numpy as np
import soundfile as sf
from scipy import signal
OUT=ROOT/'renders/v0.6.0'
NEW=ROOT/'build-v06/Release/vsl_render.exe'
OLD=ROOT/'baselines/v0.5.0/bin/vsl_render.exe'
CASES={
    '850':['--seconds','6','--rpm','850','--load','.18','--width','.8'],
    '1200':['--seconds','6','--rpm','1200','--load','.18','--width','.8'],
    '2500':['--seconds','6','--rpm','2500','--load','.85','--width','.8'],
    '5000':['--seconds','6','--rpm','5000','--load','.85','--width','.8'],
    '8000':['--seconds','6','--rpm','8000','--load','.85','--width','.8'],
    'pure5000':['--seconds','6','--rpm','5000','--load','.85','--width','.8','--pure'],
    'drive':['--seconds','30','--width','.8'],
    'neutral':['--seconds','8','--scenario','neutral','--width','.8'],
    'downshift':['--seconds','18','--scenario','downshift','--width','.8']}
BANDS=[(28,120),(120,400),(400,1200),(1200,3000),(3000,8000),(8000,14000)]
def bands(x):
    hz,p=signal.welch(x[3*48000:-1200],48000,nperseg=8192,axis=0,detrend=False)
    p=p.mean(axis=1)
    return [float(p[(hz>=lo)&(hz<hi)].sum()*48000/8192) for lo,hi in BANDS]
def main():
    OUT.mkdir(exist_ok=True);(OUT/'stems').mkdir(exist_ok=True)
    report=dict(version='0.6.0',seed=48271,comparison_runtime='frozen 0.5.0',cases={},bands_hz=BANDS)
    pure_arrays=[]
    for name,args in CASES.items():
        arrays=[];takes={}
        for tag,exe,version in [('v05',OLD,'0.5.0'),('v06',NEW,'0.6.0')]:
            extra=['--trace',str(OUT/f'{name}_{tag}.csv')]
            if name=='pure5000':extra+=['--stems',str(OUT/f'stems/pure5000_{tag}')]
            x,info=render(exe,OUT/f'{name}_{tag}.wav',args,version,extra)
            arrays.append(x);takes[tag]=info
        assert (OUT/f'{name}_v05.csv').read_bytes()==(OUT/f'{name}_v06.csv').read_bytes(),name
        copies=audition(OUT,arrays,['v05','v06'],name)
        for tag in copies:takes[tag]['audition']=copies[tag]
        takes['driver_traces_bit_identical']=True
        if name in ['850','1200','2500','5000','8000','pure5000']:
            before,after=map(bands,arrays)
            takes['spectrum']=dict(window_file_seconds=[3,5.975],old_power=before,new_power=after,
                new_minus_old_db=[float(10*np.log10(max(b,1e-30)/max(a,1e-30))) for a,b in zip(before,after)],
                limits='Rendered engineering output, not reference-aligned acoustic or perceptual fit.')
        if name=='pure5000':pure_arrays=arrays
        report['cases'][name]=takes
        print(name,'identical driver trace, rendered comparison',flush=True)
    folded=[np.repeat(x.mean(axis=1,keepdims=True),2,axis=1) for x in pure_arrays]
    copies=audition(OUT,folded,['v05','v06'],'pure5000_mono')
    report['cases']['pure5000_mono']={tag:dict(audition=copies[tag],rms_dbfs=rms(x)) for tag,x in zip(['v05','v06'],folded)}
    report['cases']['pure5000_mono']['derivation']='Arithmetic mono fold of procedural pure5000 stereo exports, duplicated to two channels, then explicitly RMS matched. No reference recording is folded.'
    report['other_templates']={}
    for profile in [1,2,3,4]:
        paths=[]
        for tag,exe,version in [('v05',OLD,'0.5.0'),('v06',NEW,'0.6.0')]:
            path=OUT/f'compat_profile{profile}_{tag}.wav'
            render(exe,path,['--profile',str(profile),'--rpm','4000','--load','.65','--seconds','3'],version);paths.append(path)
        assert paths[0].read_bytes()==paths[1].read_bytes(),profile
        report['other_templates'][str(profile)]=dict(bit_identical=True,sha256=sha(paths[0]))
    # Imported DNA bypasses factory timing, while NVH intentionally retains
    # the physical engine clock. Pure imported DNA must remain bit-identical.
    dna=OUT/'engineering_110Hz.dna';dna.write_text('VSL_DNA 1 110 4\n1 0\n0.35 0.3\n0.15 -0.7\n0.06 0.5\n')
    paths=[]
    for tag,exe,version in [('v05',OLD,'0.5.0'),('v06',NEW,'0.6.0')]:
        path=OUT/f'custom_pure_{tag}.wav'
        render(exe,path,['--rpm','5000','--load','.7','--seconds','3','--pure','--dna',str(dna)],version);paths.append(path)
    assert paths[0].read_bytes()==paths[1].read_bytes()
    report['custom_pure_bit_identical']=True
    _,report['bed714']=render(NEW,OUT/'drive_714_v06.wav',['--seconds','30','--width','.8','--channels','12'],'0.6.0',
        ['--stems',str(OUT/'stems/drive_714'),'--scene',str(OUT/'drive_714_scene.json')])
    scene_paths(OUT/'drive_714_scene.json',OUT)
    subprocess.run(['ctest','--test-dir',str(ROOT/'build-v06'),'-C','Release','--output-on-failure','--output-junit',str(OUT/'ctest.xml')],check=True)
    subprocess.run([sys.executable,str(ROOT/'tools/check_dna_pipeline.py'),'--renderer',str(NEW),'--out',str(OUT/'dna_check')],check=True)
    report['device']=smoke(ROOT/'build-v06',OUT,'0.6.0')
    report['limits']=['5.2 family technical evidence specializes firing geometry; this is not a fitted Performante model.',
        'Manifold/room propagation, cylinder balance and spectral envelopes remain engineering values.',
        'More accurate combustion timing may alter brightness/width without establishing perceptual realism.',
        'Muted device smoke and a speaker-bed file do not verify actual listening or future array playback.']
    report['files']={str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='verification.json'}
    (OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report['device'],indent=2),flush=True)
if __name__=='__main__':main()
