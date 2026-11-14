"""Fixed F3 native-time high-band relationship; no resampling or new runtime voice."""
import argparse
import os
from pathlib import Path
import shutil
import sys
p=argparse.ArgumentParser(description=__doc__)
for key in ('workspace','out'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for name in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[name]='2'
import numpy as np
import soundfile as sf
from native_cyclic_v1.measure import Coordinate,measure
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},inputs={},controls=[])


def consume(path):r['inputs'][str(path)]=sha(path);return path


def execute(name,audio,coord):
    folder=a.out/name;folder.mkdir()
    result,arrays=measure(audio,coord,plan['bands_hz'],plan['cyclic'])
    assert np.max(abs(np.asarray(result['decomposition']['cross_power'])))<plan['tolerances']['orthogonality_FS2']
    np.savez_compressed(folder/'arrays.npz',**arrays)
    save(folder/'result.json',result)
    compact={route:[v['band_hz'] for v in result[route]['bands'] if v['periodic_residual_power_supported']]
        for route in ('full','residual')}
    print(dict(name=name,supported=compact),flush=True)
    return dict(name=name,supported=compact,result=result)


try:
    for name in ['tools/run_F3_native_power_v1.py','tools/native_cyclic_v1/measure.py',
                 'research/F3_native_power_v1_plan.json','tools/research_archive_v1.py']:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    plan=load(consume(repo/'research/F3_native_power_v1_plan.json'))
    # Qualification on a known clock occurs before frozen-map or source reads.
    known_positions=.2+np.arange(14336)/(1024*67)
    coord=Coordinate(known_positions,0,43200,48000,plan['harmonics'],plan['tolerances']['minimum_QR_diagonal'])
    time=np.arange(43200)/48000;phase=(time-.2)*67
    tone=np.column_stack([.02+.2*np.cos(2*np.pi*5*phase+.1)+.1*np.sin(2*np.pi*127*phase),
                          -.01+.13*np.cos(2*np.pi*180*phase+.4)])
    coherent,residual,_=coord.decompose(tone[coord.indices])
    error=float(np.max(abs(residual)));assert error<plan['tolerances']['known_projection_FS']
    rng=np.random.default_rng(1907);noise=rng.standard_normal((43200,2))*.04
    controls={}
    for name,values in [('known_stationary',noise),('known_AM',noise*np.sqrt(1+.8*np.cos(2*np.pi*phase))[:,None])]:
        controls[name]=execute(name,values,coord)
    assert not controls['known_stationary']['supported']['residual']
    assert controls['known_AM']['supported']['residual']
    r['known_before_frozen_map']=dict(analytic_projection_error_FS=error,controls=controls)
    save(a.out/'report.json',r)
    parent=a.workspace/'baselines/F3_lift_voice_v1'
    manifest=load(consume(parent/'manifest.json'))
    source_folder=parent/'evidence/fit2/F3 Sixth Before Upshift'
    positions_path=consume(source_folder/'coordinates.npz')
    assert sha(positions_path)==next(v['sha256'] for v in manifest['files'] if v['path']==positions_path.relative_to(parent).as_posix())
    with np.load(positions_path) as f:positions=f['source_seconds'].copy()
    coord=Coordinate(positions,199.6,43200,48000,plan['harmonics'],plan['tolerances']['minimum_QR_diagonal'])
    np.savez_compressed(a.out/'coordinate.npz',source_seconds=positions,indices=coord.indices,phase=coord.phase,cycle=coord.cycles)
    prior=a.workspace/'baselines/F3_warp_noise_v1';prior_manifest=load(consume(prior/'manifest.json'))
    seeds=[1907,23117,61927,8121907]
    for seed in seeds:
        path=consume(prior/f'evidence/controls1/seed{seed}/native.npz')
        assert sha(path)==next(v['sha256'] for v in prior_manifest['files'] if v['path']==path.relative_to(prior).as_posix())
        with np.load(path) as f:
            for route,key in [('stationary','stationary'),('known_AM','modulated')]:
                r['controls'].append(execute(f'seed{seed}_{route}',f[key],coord))
        save(a.out/'report.json',r)
    # Same frozen source interval, only after all known controls have run.
    path=consume(source_folder/'native.wav')
    assert sha(path)==next(v['sha256'] for v in manifest['files'] if v['path']==path.relative_to(parent).as_posix())
    audio,rate=sf.read(path,always_2d=True);assert rate==48000 and audio.shape==(43200,2)
    np.savez_compressed(a.out/'source_native.npz',audio=audio)
    r['source']=execute('source',audio,coord)
    r.update(result='native_time_relationship_measured',source_waveform_resampled=False,
        phase_reestimated=False,new_runtime_fit=False,physical_source_separation=False,
        cyclic_law_qualified=False,full_goal='active')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
