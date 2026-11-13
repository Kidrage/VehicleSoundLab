"""Full original F3 upper temporal observations and all same-PSD controls."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha
from accel_upper_inventory_v1.temporal import observe
from idle_excitation_moments_v1.moments import describe
a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},observations=[],parent_files={})
try:
    path=repo/'research/accel_upper_temporal_v1_plan.json';plan=load(path)
    for path in [Path(__file__),path,repo/'tools/research_archive_v1.py',repo/'tools/accel_upper_inventory_v1/temporal.py',repo/'tools/idle_excitation_moments_v1/moments.py']:
        dest=a.out/'exact_sources'/path.relative_to(repo);dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][path.relative_to(repo).as_posix()]=sha(path)
    binary=np.tile([1.,-1.],24000);assert describe(binary)['excess']==-2.
    sine=np.sin(2*np.pi*np.arange(48000)*113/48000)
    assert abs(describe(sine)['excess']+1.5)<1e-12
    assert abs(describe(sine*.137)['excess']-describe(sine)['excess'])<1e-12
    parent=a.workspace/'baselines/accel_candidate_prediction_v1';manifest=load(parent/'manifest.json')
    table={v['path']:v['sha256'] for v in manifest['files']};r['parent_manifest_sha256']=sha(parent/'manifest.json')
    for case,count in [('F3_fifth1',12),('F3_fifth2',12),('F3_sixth',24)]:
        tiles=[]
        for i in range(count):
            name=f'evidence/observe1/{case}/native_{i:02d}.npz';path=parent/name
            assert sha(path)==table[name];r['parent_files'][name]=table[name]
            tiles.append(np.load(path)['audio'])
        audio=np.concatenate(tiles);folder=a.out/case;folder.mkdir()
        original,z=observe(audio,plan);np.savez_compressed(folder/'original.npz',**z)
        row=dict(segment=case,frames=len(audio),original=original,controls=[])
        fft=np.fft.rfft(audio,axis=0)
        for seed in [149921,277139,381611]:
            phase=np.random.default_rng(seed).uniform(-np.pi,np.pi,len(fft));phase[0]=phase[-1]=0.
            control=np.fft.irfft(fft*np.exp(1j*phase[:,None]),n=len(audio),axis=0)
            measured,z=observe(control,plan);np.savez_compressed(folder/f'phase_{seed}.npz',**z,phase=phase)
            reconstructed=np.fft.rfft(control,axis=0)
            assert abs(abs(reconstructed)-abs(fft)).max()<1e-10
            before=fft[:,0]*np.conj(fft[:,1]);after=reconstructed[:,0]*np.conj(reconstructed[:,1])
            assert abs(after-before).max()/max(1.,abs(before).max())<1e-12
            row['controls'].append(dict(seed=seed,statistics=measured))
        r['observations'].append(row);save(a.out/'report.json',r)
        print(dict(segment=case,original_kurtosis=original['moments']['excess'],original_CV=original['energy_CV'],
            controls_kurtosis=[v['statistics']['moments']['excess'] for v in row['controls']]),flush=True)
    r.update(result='all3_passages_and9_phase_controls_observed',plan=plan,parameter_or_audio_exported=False,
             source_identity_or_RPM_load_qualified=False,runtime_changed=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
