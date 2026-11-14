"""All-bin direct-DFT stereo audit and reporting-only endpoint diagnostics."""
import argparse
import csv
import math
import os
from pathlib import Path
import shutil
import statistics
import sys
p=argparse.ArgumentParser(description=__doc__)
for key in ('workspace','study','out'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for name in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[name]='2'
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(Path(__file__),a.out/'audit_source.py')
r=dict(result='running',cases=[])


def decision(times,power,cross,plan):
    mean=(power[:,:,0]+power[:,:,1])/2
    before=np.flatnonzero((times>=plan['baseline_seconds'][0])&(times<plan['baseline_seconds'][1]))
    base=np.array([statistics.median(mean[before,b]) for b in range(9)])
    db=10*np.log10(np.maximum(mean,1e-12)/np.maximum(base,1e-12))
    curve=np.array([statistics.median(row[b] for b in plan['primary_bands']) for row in db])
    candidates=np.flatnonzero((times>=plan['search_seconds'][0])&(times<plan['search_seconds'][1]))
    dip=min(candidates,key=lambda n:curve[n]);center=float(times[dip])
    after=np.flatnonzero((times>=center+.02)&(times<=center+.35))
    recovery=max(after,key=lambda n:curve[n])
    passed=curve[dip]<=-3 and curve[recovery]-curve[dip]>=3 and curve[recovery]>=-3
    regions={}
    for name,(lo,hi) in dict(baseline=plan['baseline_seconds'],dip=[center-.02,center+.02],post=plan['post_region_seconds']).items():
        selected=[n for n,t in enumerate(times) if lo<=t<hi]
        p=np.array([[math.fsum(float(power[n,b,c]) for n in selected)/len(selected) for c in range(2)] for b in range(9)])
        z=np.array([complex(math.fsum(float(cross[n,b].real) for n in selected),math.fsum(float(cross[n,b].imag) for n in selected))/len(selected) for b in range(9)])
        rho=z/np.sqrt(np.maximum(p[:,0]*p[:,1],1e-24))
        regions[name]=dict(power_LR=p,cross_re_im=np.column_stack([z.real,z.imag]),
            correlation_re_im=np.column_stack([rho.real,rho.imag]),
            RL_dB=10*np.log10(np.maximum(p[:,1],1e-12)/np.maximum(p[:,0],1e-12)))
    return dict(dip_center_seconds=center,dip_relative_db=float(curve[dip]),
        recovery_center_seconds=float(times[recovery]),recovery_relative_db=float(curve[recovery]),
        recovery_rise_db=float(curve[recovery]-curve[dip]),descriptive_broad_dip_recovery=bool(passed)),regions,curve,db


try:
    producer=load(a.study/'report.json');plan=load(repo/'research/F3_shift_transient_v1_plan.json')
    assert producer['result']=='fixed_F3_transient_measured'
    for name,want in producer['sources'].items():assert sha(repo/name)==want,name
    for name,want in producer['inputs'].items():assert sha(name)==want,name
    r['producer_report_sha256']=sha(a.study/'report.json')
    size=plan['window_frames'];hop=plan['hop_frames'];rate=plan['sample_rate']
    index=np.arange(size);window=.5-.5*np.cos(2*np.pi*index/size)
    bins=np.arange(size//2+1);angle=2*np.pi*bins[:,None]*index[None,:]/size
    cosine=np.cos(angle);sine=np.sin(angle)
    weights=np.full(len(bins),1/(size*np.sum(window**2)));weights[1:-1]*=2
    hz=bins*rate/size;masks=np.array([(hz>=lo)&(hz<hi) for lo,hi in plan['bands_hz']])
    errors=dict(power_FS2=0.,cross_FS2=0.,curve_dB=0.,regions=0.,parseval_FS2=0.)
    names=[v['name'] for v in producer['controls']]+['source']
    parent=a.workspace/'baselines/F3_lift_voice_v1'
    with sf.SoundFile(parent/'evidence/fit2/native_context.wav') as stream:original=stream.read(96000,always_2d=True)
    for name in names:
        with np.load(a.study/name/'arrays.npz') as f:saved={k:f[k].copy() for k in f.files}
        audio=saved['audio'];assert audio.shape==(96000,2)
        if name=='source':assert np.array_equal(audio,original)
        starts=np.arange(0,len(audio)-size+1,hop)
        assert np.array_equal(starts,saved['starts'])
        samples=audio[starts[:,None]+index[None,:]]*window[None,:,None]
        flat=samples.transpose(1,0,2).reshape(size,-1)
        z=(cosine@flat-1j*(sine@flat)).reshape(len(bins),len(starts),2).transpose(1,0,2)
        density=(z.real**2+z.imag**2)*weights[None,:,None]
        cross_bins=(z[:,:,0].real*z[:,:,1].real+z[:,:,0].imag*z[:,:,1].imag+
            1j*(z[:,:,0].real*z[:,:,1].imag-z[:,:,0].imag*z[:,:,1].real))*weights[None,:]
        powers=np.stack([density[:,keep].sum(axis=1) for keep in masks],axis=1)
        crosses=np.stack([cross_bins[:,keep].sum(axis=1) for keep in masks],axis=1)
        error=float(np.max(abs(powers-saved['power'])));assert error<2e-12
        errors['power_FS2']=max(errors['power_FS2'],error)
        error=float(np.max(abs(crosses-saved['cross'])));assert error<2e-12
        errors['cross_FS2']=max(errors['cross_FS2'],error)
        parseval=np.sum(samples**2,axis=1)/np.sum(window**2)
        error=float(np.max(abs(density.sum(axis=1)-parseval)));assert error<2e-12
        errors['parseval_FS2']=max(errors['parseval_FS2'],error)
        times=199.5+(starts+size/2)/rate;assert np.array_equal(times,saved['seconds'])
        actual,regions,curve,db=decision(times,powers,crosses,plan)
        expected=load(a.study/name/'result.json')
        for key,value in actual.items():
            if isinstance(value,bool):assert value==expected[key]
            else:assert abs(value-expected[key])<1e-9,(name,key)
        error=float(max(np.max(abs(curve-saved['primary_curve_dB'])),np.max(abs(db-saved['relative_band_dB']))));assert error<1e-7
        errors['curve_dB']=max(errors['curve_dB'],error)
        for region,fields in regions.items():
            for key,value in fields.items():
                error=float(np.max(abs(value-np.array(expected['regions'][region][key]))));assert error<1e-7
                errors['regions']=max(errors['regions'],error)
        item=dict(name=name,frames=len(starts),native_bins=len(bins),decision=actual)
        if name=='source':
            # Post-observation, reporting-only diagnostics: no new gate, selection
            # or refit. Report endpoint distances rather than call this a full event.
            item['endpoint_distances_seconds']=dict(
                dip_to_search_right=plan['search_seconds'][1]-actual['dip_center_seconds'],
                recovery_to_allowed_right=actual['dip_center_seconds']+.35-actual['recovery_center_seconds'])
            item['event_envelope_supported']=False
            item['reason']='Selected dip within half a40ms window of search end; recovery at its allowed right boundary. Acoustic event identity/timing unresolved.'
            np.savez_compressed(a.out/'source_direct_spectra.npz',seconds=times,hz=hz,density=density,cross=cross_bins)
            r['source']=item
        r['cases'].append(item);print(dict(name=name,frames=len(starts),audited=True),flush=True)
    with (parent/'source/handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    assert len(rows)==647 and all(sha(repo/v['文件'])==v['SHA-256'] for v in rows)
    voices=load(parent/'inputs/voice_files_sha256.json');assert len(voices)==74 and all(sha(repo/n)==h for n,h in voices.items())
    r.update(result='direct_native_transient_audit_passed',maximum_errors=errors,
        C_H_exact=647,voice_files_exact=74,source_original_samples_exact=True,
        physical_shift_timing_or_envelope_qualified=False,full_goal='active')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r['maximum_errors'])
