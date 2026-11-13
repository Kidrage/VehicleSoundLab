"""Compile unchanged fine-static source parameters to isolated C; verify sound and timing."""
import argparse,json,shutil,subprocess,sys,time,xml.etree.ElementTree as ET
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha
from modal_texture_v1.voice import render
from sustain_osc_v1.oracle import Gaussian

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},commands=[],comparisons=[],timing=[])


def command(label,args):
    args=list(map(str,args));began=time.perf_counter();done=subprocess.run(args,cwd=repo,capture_output=True,timeout=240)
    dest=a.out/(label+'.log');dest.write_bytes(done.stdout+done.stderr)
    row=dict(label=label,args=args,return_code=done.returncode,seconds=time.perf_counter()-began,log_sha256=sha(dest))
    r['commands'].append(row);save(a.out/'report.json',r);print(json.dumps(row),flush=True)
    if done.returncode:raise RuntimeError(str(dest))
    return done.stdout


def export(root,modal,amplitude,fine):
    root.mkdir()
    lines=[f'VSL_MODAL_SOURCE 1 48000 {len(modal["frequencies_hz"])}']
    for hz,amp,phi in zip(modal['frequencies_hz'],modal['amplitude_LR'],modal['initial_phase_LR']):
        lines.append(' '.join(f'{v:.17g}' for v in [hz,*amp,*phi]))
    (root/'core.msource').write_text('\n'.join(lines)+'\n',encoding='ascii',newline='\n')
    lines=[f'VSL_MODAL_TEXTURE 1 48000 {len(amplitude["factor"])} {amplitude["hop_frames"]} {amplitude["alpha"]:.17g}']
    lines+=[' '.join(f'{v:.17g}' for v in row) for row in amplitude['factor']]
    (root/'core.mtexture').write_text('\n'.join(lines)+'\n',encoding='ascii',newline='\n')
    lines=[f'VSL_SPECTRAL_TEXTURE 1 48000 {len(fine["kernels"])} {fine["warmup_frames"]}']
    for band in fine['kernels']:
        taps=band['taps'];lines.append(f'{len(taps)} {band["gain"]:.17g} {band["right_over_left"]:.17g}')
        lines+=[' '.join(f'{v:.17g}' for v in taps[i:i+8]) for i in range(0,len(taps),8)]
    (root/'fine.sfir').write_text('\n'.join(lines)+'\n',encoding='ascii',newline='\n')


def run(root,label,frames,seed,ratio,amount,chunk=240,controls=False):
    prefix=root/label
    raw=command(label,[exe,root/'core.msource',root/'core.mtexture',root/'fine.sfir',prefix,
        frames/48000,seed,ratio,amount,chunk,'controls' if controls else 'static'])
    timing=json.loads(raw.decode().strip());assert timing['frames']==frames and timing['all_C'] and not timing['room']
    r['timing'].append(dict(id=label,**timing));return prefix


def compare(prefix,expected,label):
    for bus,y in expected.items():
        path=Path(str(prefix)+'_'+bus+'.wav');x,rate=sf.read(path,always_2d=True)
        assert rate==48000 and x.shape==y.shape and np.isfinite(x).all()
        error=float(abs(x-y).max());assert error<=1e-7,(label,bus,error)
        r['comparisons'].append(dict(id=label,bus=bus,frames=len(x),maximum_FS_error=error,sha256=sha(path)))
    save(a.out/'report.json',r)


try:
    sources={Path(__file__),repo/'research/spectral_texture_c_v1_plan.json',repo/'tools/research_archive_v1.py',
        repo/'tools/sustain_osc_v1/oracle.py',repo/'tools/idle_modal_v1/modal.py',repo/'tools/idle_texture_v2/dynamics.py'}
    for folder in ['modules/partitioned_fir','modules/spectral_texture','modules/modal_source','modules/modal_texture',
        'modules/resonant_detail','modules/resonant_detail_io','experiments/spectral_texture_v1',
        'experiments/modal_texture_v1','experiments/modal_idle_v1','tools/modal_texture_v1']:
        sources.update(p for p in (repo/folder).iterdir() if p.is_file())
    sources.update(repo/p for p in ['src/io/file.c','src/io/file.h','src/io/wav.c','src/io/wav.h'])
    for path in sorted(sources):
        name=path.relative_to(repo);dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][name.as_posix()]=sha(path)
    build=repo/'build-spectral-texture-v1'
    command('configure',['cmake','-S','experiments/spectral_texture_v1','-B',build,'-A','x64'])
    command('build',['cmake','--build',build,'--config','Release','--parallel','2'])
    command('ctest',['ctest','--test-dir',build,'-C','Release','--output-on-failure','--output-junit',a.out/'ctest.xml'])
    tree=ET.parse(a.out/'ctest.xml').getroot();assert len(tree.findall('.//testcase'))==4 and not tree.findall('.//failure')
    exe=build/'Release/fine_idle_probe.exe'
    for name in ['fine_idle_probe','spectral_texture_checks']:shutil.copy2(build/f'Release/{name}.exe',a.out/f'{name}.exe')
    shutil.copy2(build/'CMakeCache.txt',a.out/'CMakeCache.txt')
    # Unrelated known sources before reading saved source-derived parameters.
    modal=dict(frequencies_hz=[83.17,193.41],amplitude_LR=[[.2,.1],[.03,.04]],initial_phase_LR=[[.1,.3],[.2,-.1]])
    factor=np.array([[.1,0],[.04,.07]])
    amplitude=dict(covariance=(factor@factor.T).tolist(),factor=factor.tolist(),alpha=.7,hop_frames=97)
    fine=dict(warmup_frames=13,kernels=[dict(taps=[.8,.6],gain=.01,right_over_left=.7),dict(taps=[.8,.6],gain=.03,right_over_left=-.3)])
    root=a.out/'known';export(root,modal,amplitude,fine);frames=2051;seed=149921
    prefix=run(root,'known',frames,seed,1.1,.5)
    main,_,_=render(modal,amplitude,frames,48000,seed,.5,1.1);detail=np.zeros_like(main)
    for i,band in enumerate(fine['kernels']):
        rng=Gaussian(seed^(0x9E3779B97F4A7C15*(i+1)&((1<<64)-1)))
        noise=np.fromiter((rng.next() for _ in range(frames+13)),float)
        mono=np.convolve(noise,band['taps'])[13:frames+13]*band['gain']
        detail+=mono[:,None]*np.array([[1.,band['right_over_left']]])
    compare(prefix,dict(core=main,detail=detail,mix=main+detail),'known')
    old=a.workspace/'baselines/modal_texture_c_v1/inputs';invariants={}
    for name in ['C_files_sha256.json','voice_files_sha256.json']:
        files=load(old/name);assert all(sha(repo/key)==value for key,value in files.items())
        invariants[name]=len(files)
    parent=a.workspace/'baselines/modal_texture_v1/evidence/trial1'
    fine_path=a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json'
    profile=load(parent/'profile.json');modal=profile['modal'];amplitude=profile['envelope'];fine=load(fine_path)
    r.update(parent_profile_sha256=sha(parent/'profile.json'),fine_profile_sha256=sha(fine_path))
    root=a.out/'F2';export(root,modal,amplitude,fine)
    for seed in [149921,277139,381611]:
        detail=sf.read(parent/f'fixed_detail_{seed}.wav',always_2d=True)[0]
        for amount in [0.,.5,1.]:
            label=f'F2_{seed}_{round(amount*100):03d}'
            prefix=run(root,label,576000,seed,1.,amount)
            expected=dict(core=sf.read(parent/f'core_{round(amount*100):03d}_{seed}.wav',always_2d=True)[0],
                detail=detail,mix=sf.read(parent/f'mix_{round(amount*100):03d}_{seed}.wav',always_2d=True)[0])
            compare(prefix,expected,label)
    # All meaningful control events are sample-located, not block-located.
    first=run(root,'controls_1',96031,149921,1.,.5,1,True)
    second=run(root,'controls_479',96031,149921,1.,.5,479,True)
    for bus in ['core','detail','mix']:
        assert Path(str(first)+'_'+bus+'.wav').read_bytes()==Path(str(second)+'_'+bus+'.wav').read_bytes()
    actual,_=sf.read(Path(str(first)+'_detail.wav'),always_2d=True)
    expected,_=sf.read(root/'F2_149921_050_detail.wav',always_2d=True)
    assert np.array_equal(actual,expected[:len(actual)])
    sustained=run(root,'sustained_30s',30*48000,149921,1.,.5)
    for bus in ['core','detail','mix']:
        x,_=sf.read(Path(str(sustained)+'_'+bus+'.wav'),always_2d=True)
        y,_=sf.read(root/f'F2_149921_050_{bus}.wav',always_2d=True);assert np.array_equal(x[:len(y)],y)
    r.update(result='full_isolated_C_fine_static_idle_passed_pending_listening',tests=4,
        comparisons_count=len(r['comparisons']),maximum_FS_error=max(v['maximum_FS_error'] for v in r['comparisons']),
        source_parameters_changed=False,old_C_and_voice_files_unchanged=invariants,all_C_core_detail_mix=True,
        blocks1_479_exact=True,control_detail_independent=True,sustained_prefix_exact=True,
        listening_accepted=False,driver_integrated=False,device_verified=False,hard_realtime_certified=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(json.dumps(dict(result=r['result'],maximum_FS_error=r.get('maximum_FS_error'),tests=r.get('tests'))),flush=True)
