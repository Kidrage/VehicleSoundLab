"""Paired stationary-noise controls through immutable F3 resampling coordinates."""
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
from research_archive_v1 import load,save,sha
from exterior_clock_v1.warp import render_positions
from cyclic_detail_v1.measure import split,dependence

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},inputs={},cases=[])

def consume(path):r['inputs'][str(path)]=sha(path);return path

try:
    for name in ('tools/run_F3_warp_noise_v1.py','research/F3_warp_noise_v1_plan.json',
        'research/F3_detail_v1_plan.json','tools/research_archive_v1.py',
        'tools/exterior_clock_v1/warp.py','tools/cyclic_detail_v1/measure.py'):
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    plan=load(consume(repo/'research/F3_warp_noise_v1_plan.json'))
    analysis=load(consume(repo/'research/F3_detail_v1_plan.json'))
    # Independent analytic DC/tones under known monotonic maps, before loading
    # the source-derived map. This does not qualify all of the phase extractor.
    rate=plan['native_context']['rate'];known_time=np.arange(rate)/rate
    u=np.linspace(0,1,14336);known_maps={
        'affine':.25+.45*u,
        'smooth':.25+.45*u+.001*np.sin(8*np.pi*u)}
    known_audio=np.column_stack([.2*np.sin(2*np.pi*997*known_time),
        .17*np.cos(2*np.pi*1703*known_time)])
    known=[]
    for name,at in known_maps.items():
        assert np.min(np.diff(at))>0
        constant=render_positions(np.full((rate,2),.12),0,at,10000)
        tones=render_positions(known_audio,0,at,10000)
        truth=np.column_stack([.2*np.sin(2*np.pi*997*at),.17*np.cos(2*np.pi*1703*at)])
        errors=dict(map=name,constant_max_FS=float(np.max(abs(constant-.12))),
            tone_max_FS=float(np.max(abs(tones-truth))))
        assert max(errors['constant_max_FS'],errors['tone_max_FS'])<plan['known_fixture_tolerance_FS']
        known.append(errors)
    r['known_before_map']=dict(analytic_resampling=known,
        stationary_native_variance=plan['noise_sigma']**2,
        stationary_native_cross_at_declared_delay=plan['noise_sigma']**2*plan['right_delayed_left_fraction'])
    parent=a.workspace/'baselines/F3_lift_voice_v1';manifest=load(consume(parent/'manifest.json'))
    folder=parent/'evidence/fit2/F3 Sixth Before Upshift'
    for name in ('coordinates.npz','extraction.json'):
        path=consume(folder/name)
        assert sha(path)==next(v['sha256'] for v in manifest['files'] if v['path']==path.relative_to(parent).as_posix())
    with np.load(folder/'coordinates.npz') as f:positions=f['source_seconds'].copy()
    info=load(folder/'extraction.json')['extraction'];root=info['root_hz'];cutoff=info['phase']['source_cutoff_hz']
    assert len(positions)==14336 and np.all(np.diff(positions)>0)
    affine=np.linspace(positions[0],positions[-1],len(positions))
    start,stop=plan['native_context']['seconds'];rate=plan['native_context']['rate'];frames=round((stop-start)*rate)
    native_times=start+np.arange(frames)/rate;canonical=np.arange(len(positions))/1024
    known_phase=np.interp(native_times,positions,canonical)
    before=native_times<positions[0];after=native_times>positions[-1]
    known_phase[before]=canonical[0]+(native_times[before]-positions[0])/(positions[1]-positions[0])/1024
    known_phase[after]=canonical[-1]+(native_times[after]-positions[-1])/(positions[-1]-positions[-2])/1024
    np.savez_compressed(a.out/'coordinates.npz',actual=positions,affine=affine,native_times=native_times,known_AM_cycles=known_phase)
    r.update(root_hz=root,cutoff_hz=cutoff,frames=len(positions),native_frames=frames,
        conditional_map_only=True,new_source_waveform_read=False,reestimated_phase=False)
    for seed in plan['noise_seeds']:
        folder=a.out/f'seed{seed}';folder.mkdir()
        rng=np.random.default_rng(seed);delay=plan['delay_frames'];left=rng.standard_normal(frames+delay)
        independent=rng.standard_normal(frames);rho=plan['right_delayed_left_fraction']
        native=plan['noise_sigma']*np.column_stack([left[delay:],rho*left[:-delay]+np.sqrt(1-rho*rho)*independent])
        amplitude=np.sqrt(1+plan['AM_depth']*np.cos(2*np.pi*known_phase))
        modulated=native*amplitude[:,None]
        np.savez_compressed(folder/'native.npz',stationary=native,modulated=modulated)
        routes={
            'direct_canonical':native[:len(positions)].copy(),
            'same_endpoints_affine_map':render_positions(native,start,affine,cutoff),
            'actual_frozen_map':render_positions(native,start,positions,cutoff),
            'known_AM_actual_frozen_map':render_positions(modulated,start,positions,cutoff)}
        for route,values in routes.items():
            coherent,residual,decomposition=split(values,1024)
            stats=dependence(residual,root,analysis['bands_hz'],analysis['cyclic'])
            np.savez_compressed(folder/(route+'.npz'),canonical=values,coherent=coherent,residual=residual)
            supported=[v['band_hz'] for v in stats['bands'] if v['periodic_residual_power_supported']]
            row=dict(seed=seed,route=route,decomposition=decomposition,dependence=stats,supported_bands=supported)
            r['cases'].append(row);save(a.out/'report.json',r)
            print(dict(seed=seed,route=route,supported=supported),flush=True)
    r['route_summary']={route:dict(seeds=len(plan['noise_seeds']),
        any_support=sum(bool(v['supported_bands']) for v in r['cases'] if v['route']==route),
        high8_14_support=sum(any(b[0]>=8000 for b in v['supported_bands']) for v in r['cases'] if v['route']==route)) for route in plan['routes']}
    r.update(result='paired_frozen_map_controls_completed',physical_source_separation=False,runtime_changed=False,hearing=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r.get('route_summary'))
