"""Port frozen fast-detail candidates to C, without fitting or default promotion."""
import argparse,json,math,shutil,subprocess,sys,time,xml.etree.ElementTree as ET
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha
from sustain_osc_v1.oracle import Gaussian
a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},commands=[],comparisons=[],timing=[])


def command(label,args,timeout=240):
    args=list(map(str,args));begin=time.perf_counter();done=subprocess.run(args,cwd=repo,capture_output=True,timeout=timeout)
    path=a.out/(label+'.log');path.write_bytes(done.stdout+done.stderr)
    row=dict(label=label,args=args,return_code=done.returncode,seconds=time.perf_counter()-begin,log_sha256=sha(path))
    r['commands'].append(row);save(a.out/'report.json',r);print(row,flush=True)
    if done.returncode:raise RuntimeError(str(path))
    return done.stdout


def export(root,modal,motion,fine):
    root.mkdir();lines=[f'VSL_MODAL_SOURCE 1 48000 {len(modal["frequencies_hz"])}']
    for f,amp,phase in zip(modal['frequencies_hz'],modal['amplitude_LR'],modal['initial_phase_LR']):lines.append(' '.join(f'{v:.17g}' for v in [f,*amp,*phase]))
    (root/'core.msource').write_text('\n'.join(lines)+'\n',encoding='ascii',newline='\n')
    lines=[f'VSL_MODAL_TEXTURE 1 48000 {len(motion["factor"])} {motion["hop_frames"]} {motion["alpha"]:.17g}']
    lines+=[' '.join(f'{v:.17g}' for v in row) for row in motion['factor']]
    (root/'fast.mtexture').write_text('\n'.join(lines)+'\n',encoding='ascii',newline='\n')
    lines=[f'VSL_SPECTRAL_TEXTURE 1 48000 {len(fine["kernels"])} {fine["warmup_frames"]}']
    for band in fine['kernels']:
        taps=band['taps'];lines.append(f'{len(taps)} {band["gain"]:.17g} {band["right_over_left"]:.17g}')
        lines+=[' '.join(f'{v:.17g}' for v in taps[i:i+8]) for i in range(0,len(taps),8)]
    (root/'fine.sfir').write_text('\n'.join(lines)+'\n',encoding='ascii',newline='\n')


def run(root,label,frames,seed,amount,chunk=240,mode='static'):
    prefix=root/label;raw=command(label,[exe,root/'core.msource',root/'fast.mtexture',root/'fine.sfir',prefix,frames/48000,seed,1,amount,chunk,mode])
    timing=json.loads(raw.decode().strip());assert timing['frames']==frames and timing['all_C'] and not timing['room']
    r['timing'].append(dict(id=label,**timing));return prefix


def compare(prefix,expected,label):
    for bus,y in expected.items():
        path=Path(str(prefix)+'_'+bus+'.wav');x,rate=sf.read(path,always_2d=True)
        assert rate==48000 and x.shape==y.shape and np.isfinite(x).all()
        error=float(abs(x-y).max());assert error<=1e-7,(label,bus,error)
        r['comparisons'].append(dict(id=label,bus=bus,maximum_FS_error=error,frames=len(x),sha256=sha(path)))


try:
    parent=a.workspace/'baselines/idle_microtexture_v1';invariants={}
    for name in ['C_files_sha256.json','voice_files_sha256.json']:
        files=load(parent/'inputs'/name);assert all(sha(repo/key)==value for key,value in files.items());invariants[name]=len(files)
    sources={Path(__file__),repo/'research/idle_microtexture_c_v1_plan.json',repo/'tools/research_archive_v1.py',
        repo/'Build-Fast-Idle-Study.ps1',repo/'Launch-Fast-Idle-Study.cmd',repo/'tools/sustain_osc_v1/oracle.py'}
    for folder in ['modules/spectral_motion','modules/modal_source','modules/modal_texture','modules/spectral_texture',
        'modules/partitioned_fir','modules/resonant_detail','modules/resonant_detail_io','modules/win_output',
        'experiments/idle_microtexture_v1','experiments/spectral_texture_v1','experiments/modal_texture_v1','experiments/modal_idle_v1']:
        sources.update(path for path in (repo/folder).iterdir() if path.is_file())
    sources.update(repo/path for path in ['src/io/file.c','src/io/file.h','src/io/wav.c','src/io/wav.h'])
    for path in sorted(sources):
        name=path.relative_to(repo);dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest);r['sources'][name.as_posix()]=sha(path)
    build=repo/'build-idle-microtexture-v1'
    command('configure',['cmake','-S','experiments/idle_microtexture_v1','-B',build,'-A','x64'])
    command('build',['cmake','--build',build,'--config','Release','--parallel','2'])
    command('ctest',['ctest','--test-dir',build,'-C','Release','--output-on-failure','--output-junit',a.out/'ctest.xml'])
    tree=ET.parse(a.out/'ctest.xml').getroot();assert len(tree.findall('.//testcase'))==6 and not tree.findall('.//failure')
    exe=build/'Release/fast_idle_probe.exe'
    for name in ['fast_idle_probe','spectral_motion_checks','fast_idle_monitor_checks','fast_idle_device','VslFastIdleMonitor']:shutil.copy2(build/f'Release/{name}.exe',a.out/f'{name}.exe')
    shutil.copy2(build/'CMakeCache.txt',a.out/'CMakeCache.txt')
    # Unrelated source/filter/stereo fixture before loading source-derived coefficients.
    modal=dict(frequencies_hz=[83.17,193.41],amplitude_LR=[[.2,.1],[.03,.04]],initial_phase_LR=[[.1,.3],[.2,-.1]])
    factor=np.array([[.1,0],[.04,.07]]);motion=dict(factor=factor.tolist(),alpha=.7,hop_frames=97)
    fine=dict(warmup_frames=13,kernels=[dict(taps=[.8,.6],gain=.01,right_over_left=.7),dict(taps=[.8,.6],gain=.03,right_over_left=-.3)])
    root=a.out/'known';export(root,modal,motion,fine);n=2051;seed=149921;amount=.5
    prefix=run(root,'known',n,seed,amount);timegrid=np.arange(n)/48000
    core=sum(np.array(amp)*np.cos(2*np.pi*f*timegrid[:,None]+np.array(phase)) for f,amp,phase in zip(modal['frequencies_hz'],modal['amplitude_LR'],modal['initial_phase_LR']))
    count=(n-1)//97+2;rng=Gaussian(seed^0x8CB92BA72F3D8DD7);normal=np.array([rng.next() for _ in range(count*2)]).reshape(count,2)
    state=np.empty_like(normal)
    for i,z in enumerate(normal):
        innovation=np.array([math.fsum(row*z) for row in factor]);state[i]=innovation if i==0 else .7*state[i-1]+math.sqrt(1-.7**2)*innovation
    u=(1-np.cos(np.pi*(np.arange(n)%97)/97))/2;at=np.arange(n)//97
    value=((1-u[:,None])*state[at]+u[:,None]*state[at+1])/np.sqrt(((1-u)**2+u*u+2*.7*u*(1-u))[:,None])
    gain=np.exp(amount*value-amount**2*np.diag(factor@factor.T));detail=np.zeros_like(core)
    for i,band in enumerate(fine['kernels']):
        rng=Gaussian(seed^(0x9E3779B97F4A7C15*(i+1)&((1<<64)-1)));noise=np.array([rng.next() for _ in range(n+13)])
        mono=np.convolve(noise,band['taps'])[13:n+13]*band['gain']*gain[:,i]
        detail+=mono[:,None]*np.array([[1.,band['right_over_left']]])
    compare(prefix,dict(core=core,detail=detail,mix=core+detail),'known')
    frozen=parent/'evidence/trial1';fast=load(frozen/'profile.json')
    base=load(parent/'inputs/F2_parent_profile.json');root=a.out/'F2';export(root,base['modal'],fast['envelope'],base)
    assert sha(root/'fast.mtexture')==sha(repo/'experiments/idle_microtexture_v1/F2_fast_detail.mtexture')
    for seed in [149921,277139,381611]:
        core,_=sf.read(frozen/f'core_{seed}.wav',always_2d=True)
        for amount in [0.,.5,1.]:
            label=f'{round(amount*100):03d}_{seed}';prefix=run(root,'F2_'+label,576000,seed,amount)
            expected=dict(core=core,detail=sf.read(frozen/f'detail_{label}.wav',always_2d=True)[0],mix=sf.read(frozen/f'mix_{label}.wav',always_2d=True)[0])
            compare(prefix,expected,label)
    one=run(root,'controls_1',96031,149921,.5,1,'controls');other=run(root,'controls_479',96031,149921,.5,479,'controls')
    for bus in ['core','detail','mix']:assert Path(str(one)+'_'+bus+'.wav').read_bytes()==Path(str(other)+'_'+bus+'.wav').read_bytes()
    core,_=sf.read(Path(str(one)+'_core.wav'),always_2d=True);static,_=sf.read(root/'F2_050_149921_core.wav',always_2d=True);assert np.array_equal(core,static[:len(core)])
    long=run(root,'sustained_30s',1440000,149921,.5)
    for bus in ['core','detail','mix']:
        x,_=sf.read(Path(str(long)+'_'+bus+'.wav'),always_2d=True);y,_=sf.read(root/f'F2_050_149921_{bus}.wav',always_2d=True);assert np.array_equal(x[:len(y)],y)
    raw=command('device',[build/'Release/fast_idle_device.exe',repo,a.out/'device'],timeout=60)
    device=json.loads(raw.decode().strip());assert device['result']=='pass' and device['offline_exact'] and device['muted'];r['device']=device
    assert all(sha(repo/key)==value for name in ['C_files_sha256.json','voice_files_sha256.json'] for key,value in load(parent/'inputs'/name).items())
    r.update(result='isolated_fast_detail_C_and_muted_device_verified',tests=6,all9_frozen_candidates_checked=True,
        maximum_FS_error=max(row['maximum_FS_error'] for row in r['comparisons']),old_C_and_voices_exact=invariants,
        sample_controls1_479_byte_exact=True,core_unchanged_by_detail_controls=True,sustained30s_prefix_exact=True,
        room=False,timbre_accepted=False,driver_integrated=False,hard_realtime_certified=False,native_UI_manual_verified=False,
        parent_manifest_sha256=sha(parent/'manifest.json'))
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],maximum_FS_error=r.get('maximum_FS_error')),flush=True)
