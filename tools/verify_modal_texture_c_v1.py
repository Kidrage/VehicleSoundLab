"""Isolated C amplitude port: old controls plus unchanged Python/full frozen oracles."""
import argparse,json,shutil,subprocess,sys,time,xml.etree.ElementTree as ET
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from modal_texture_v1.voice import render
from modal_texture_v1.envelope import states,gains
from research_archive_v1 import sha,load,save

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},commands=[],comparisons=[],driver_changed=False,all_C_mix=False)


def command(label,args):
    args=list(map(str,args));start=time.perf_counter()
    done=subprocess.run(args,cwd=repo,capture_output=True,timeout=240)
    path=a.out/(label+'.log');path.write_bytes(done.stdout+done.stderr)
    r['commands'].append(dict(label=label,command=args,return_code=done.returncode,
        seconds=time.perf_counter()-start,log_sha256=sha(path)))
    save(a.out/'report.json',r);print(json.dumps(r['commands'][-1]),flush=True)
    if done.returncode:raise RuntimeError(f'{label} failed; see {path}')


def export(name,modal,envelope):
    root=a.out/name;root.mkdir();n=len(envelope['factor'])
    lines=[f'VSL_MODAL_TEXTURE 1 48000 {n} {envelope["hop_frames"]} {envelope["alpha"]:.17g}']
    lines += [' '.join(f'{v:.17g}' for v in row) for row in envelope['factor']]
    (root/'texture.mtexture').write_text('\n'.join(lines)+'\n',encoding='ascii')
    lines=[f'VSL_MODAL_SOURCE 1 48000 {n}']
    for f,am,ph in zip(modal['frequencies_hz'],modal['amplitude_LR'],modal['initial_phase_LR']):
        lines.append(' '.join(f'{v:.17g}' for v in [f,*am,*ph]))
    (root/'source.msource').write_text('\n'.join(lines)+'\n',encoding='ascii')
    return root


def compare(root,modal,model,seed,amount,frames,ratio=1.,dump=False,frozen=None):
    label=f'{root.name}_{seed}_{round(amount*100):03d}_{ratio}'
    output=root/f'core_{round(amount*100):03d}_{seed}_{ratio}.wav'
    args=[exe,root/'source.msource',root/'texture.mtexture',output,frames/48000,seed,ratio,amount]
    if dump:args.append(root/'gains.f64')
    command(label,args);actual,rate=sf.read(output,always_2d=True)
    expected,state,_=render(modal,model,frames,48000,seed,amount,ratio)
    error=float(abs(actual-expected).max())
    assert rate==48000 and actual.shape==(frames,2) and np.isfinite(actual).all() and error<=1e-7
    row=dict(id=label,seed=seed,amount=amount,ratio=ratio,frames=frames,
        maximum_FS_error=error,peak=float(abs(actual).max()),sha256=sha(output))
    if dump:
        observed=np.fromfile(root/'gains.f64',dtype='<f8').reshape(frames,-1)
        expected_gain=gains(model,state,frames,amount);delta=float(abs(observed-expected_gain).max())
        assert delta<=1e-12,delta;row['maximum_gain_error']=delta
    if frozen:
        y,other_rate=sf.read(frozen,always_2d=True);assert other_rate==48000 and y.shape==actual.shape
        delta=float(abs(actual-y).max());assert delta<=1e-7
        row['frozen_FLOAT_error']=delta;row['frozen_sha256']=sha(frozen)
    r['comparisons'].append(row);save(a.out/'report.json',r)


try:
    sources={Path(__file__),repo/'research/modal_texture_c_v1_plan.json',
        repo/'tools/research_archive_v1.py',repo/'tools/sustain_osc_v1/oracle.py',
        repo/'tools/idle_modal_v1/modal.py'}
    for folder in ['modules/modal_source','modules/modal_texture','experiments/modal_texture_v1',
        'experiments/modal_idle_v1','modules/resonant_detail','modules/resonant_detail_io','tools/modal_texture_v1']:
        sources.update(path for path in (repo/folder).iterdir() if path.is_file())
    sources.update(repo/path for path in ['src/io/file.c','src/io/file.h','src/io/wav.c','src/io/wav.h'])
    for path in sorted(sources):
        name=path.relative_to(repo);dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][name.as_posix()]=sha(path)
    build=repo/'build-modal-texture-v1'
    command('configure',['cmake','-S','experiments/modal_texture_v1','-B',build,'-A','x64'])
    command('build',['cmake','--build',build,'--config','Release','--parallel','2'])
    command('ctest',['ctest','--test-dir',build,'-C','Release','--output-on-failure','--output-junit',a.out/'ctest.xml'])
    tree=ET.parse(a.out/'ctest.xml').getroot();assert len(tree.findall('.//testcase'))==3 and not tree.findall('.//failure')
    exe=build/'Release/modal_texture_probe.exe'
    for name in ['modal_texture_probe','modal_texture_checks']:
        shutil.copy2(build/f'Release/{name}.exe',a.out/f'{name}.exe')
    shutil.copy2(build/'CMakeCache.txt',a.out/'CMakeCache.txt')
    # Known unrelated timbre first, before the saved F2 parameter input.
    modal=dict(frequencies_hz=[83.17,193.41],amplitude_LR=[[.2,.1],[.03,.04]],initial_phase_LR=[[.1,.3],[.2,-.1]])
    factor=np.array([[.1,0],[.04,.07]])
    model=dict(covariance=(factor@factor.T).tolist(),factor=factor.tolist(),alpha=.7,hop_frames=97)
    root=export('known',modal,model)
    compare(root,modal,model,149921,.5,12347,1.1,True)
    zero=dict(model,factor=np.zeros((2,2)).tolist(),covariance=np.zeros((2,2)).tolist())
    root=export('known_zero',modal,zero);compare(root,modal,zero,277139,1,12347,.9,True)
    singular=dict(model,factor=[[.12,0],[.12,0]],covariance=[[.0144,.0144],[.0144,.0144]])
    root=export('known_singular',modal,singular);compare(root,modal,singular,0x8CB92BA72F3D8DD7,1,12347,1.,True)
    parent=a.workspace/'references/analysis/modal_texture_v1/trial1'
    frozen=a.workspace/'baselines/modal_texture_v1/evidence/trial1'
    assert sha(parent/'profile.json')==sha(frozen/'profile.json')
    profile=load(parent/'profile.json');modal=profile['modal'];model=profile['envelope']
    root=export('F2',modal,model);r['source_profile_sha256']=sha(parent/'profile.json')
    for seed in [149921,277139,381611]:
        for amount in [0.,.5,1.]:
            baseline=parent/f'core_{round(amount*100):03d}_{seed}.wav'
            assert sha(baseline)==sha(frozen/baseline.name)
            compare(root,modal,model,seed,amount,576000,frozen=baseline)
    for ratio in [.9,1.1]:compare(root,modal,model,149921,.5,48031,ratio)
    # Full mixed audition uses the identical Python fine-static detail bus.
    # This check establishes C-core transfer only, not an all-C filter port.
    for seed in [149921,277139,381611]:
        detail,rate=sf.read(parent/f'fixed_detail_{seed}.wav',always_2d=True);assert rate==48000
        for amount in [0.,.5,1.]:
            main,_=sf.read(root/f'core_{round(amount*100):03d}_{seed}_1.0.wav',always_2d=True)
            mix=main+detail;expected,_=sf.read(parent/f'mix_{round(amount*100):03d}_{seed}.wav',always_2d=True)
            delta=float(abs(mix-expected).max());assert delta<=1e-7 and abs(mix).max()<1
            out=root/f'hybrid_{round(amount*100):03d}_{seed}.wav';sf.write(out,mix,48000,subtype='FLOAT')
    r.update(result='isolated_C_amplitude_kernel_passed_pending_listening',tests=3,
        maximum_FS_error=max(row['maximum_FS_error'] for row in r['comparisons']),
        maximum_gain_error=max(row.get('maximum_gain_error',0) for row in r['comparisons']),
        all_frozen_core_groups=9,known_control_groups=3,pitch_check_groups=2,hybrid_groups=9,
        common_LR_amplitude=True,phase_modulation=False,frequency_modulation=False,room=False,
        listening_accepted=False,full_realtime_filter_certified=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(json.dumps(dict(result=r['result'],maximum_FS_error=r.get('maximum_FS_error'),tests=r.get('tests'))),flush=True)
