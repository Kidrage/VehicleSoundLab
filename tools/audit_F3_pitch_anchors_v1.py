"""Independent native/path/coordinate/marginal-covariance and seeded-C audit.

SVD replay is explicitly a reproducibility check, not independent SVD proof.
Earlier ill-conditioned absolute residual-ratio failures are not reclassified.
"""
import argparse
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha

p=argparse.ArgumentParser(description=__doc__)
for key in ('workspace','fit','out'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[key]='2'
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from local_voice_batch_v1.audit_kernels import peaks,path,coordinates,rebuild,coherence,seeded_samples
from local_voice_batch_v1.bandlimited_controls import float_error
from decel_source_v1.aperture import extract
from sound_dna.windowed import estimate
from sound_dna.profile import export
from idle_texture_v1.profile import load as model_load

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},inputs={},cases=[])


def consume(p):r['inputs'][str(p)]=sha(p);return p


try:
    names=['tools/audit_F3_pitch_anchors_v1.py','tools/local_voice_batch_v1/audit_kernels.py',
        'tools/local_voice_batch_v1/bandlimited_controls.py','tools/idle_texture_v1/profile.py',
        'tools/sustain_osc_v1/oracle.py','tools/decel_source_v1/aperture.py','tools/exterior_clock_v1/warp.py',
        'tools/research_archive_v1.py']
    names += [v.relative_to(repo).as_posix() for v in (repo/'tools/sound_dna').glob('*.py')]
    for name in sorted(set(names)):
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    # DFT-aligned real stereo tone: finite Hann power and signed cross exactly.
    t=np.arange(16384)/48000;w=.5-.5*np.cos(2*np.pi*np.arange(16384)/16384)
    tone=np.column_stack((.2*np.cos(2*np.pi*375*t),.12*np.cos(2*np.pi*375*t+.4)))
    z=np.fft.rfft(tone*w[:,None],axis=0);power=abs(z)**2/(48000*math.fsum(w*w))
    cross=z[:,0]*z[:,1].conj()/(48000*math.fsum(w*w));power[1:-1]*=2;cross[1:-1]*=2
    err=max(abs(math.fsum(power[:,c])*48000/16384-amp**2/2) for c,amp in enumerate((.2,.12)))
    assert err<1e-14 and abs(sum(cross)*48000/16384-.2*.12/2*np.exp(-.4j))<1e-14
    r['known_before_source']=dict(power_error_FS2=err,signed_cross='L*conj(R)')
    fit=load(consume(a.fit/'report.json'));plan=load(consume(repo/'research/F3_pitch_anchors_v1_plan.json'))
    assert fit['result']=='fixed_F3_pitch_anchors_checked'
    assert fit['known_bandlimited_before_source']['result']=='known_bandlimited_PRNG_and_stereo_C_passed'
    for name,h in fit['sources'].items():assert sha(repo/name)==h==sha(a.fit/'exact_sources'/name)
    for name,h in fit['inputs'].items():assert sha(consume(Path(name)))==h
    registry=load(consume(a.workspace/'references/segments_v1.json'))
    assert sha(repo/'references/segments_v1.json')==sha(a.workspace/'references/segments_v1.json')
    master=a.workspace/registry['sources']['F3']['master']
    window=.5-.5*np.cos(2*np.pi*np.arange(3840)/3840);all_hz=np.arange(8193)*48000/16384
    bands=((28,120),(120,400),(400,1200),(1200,3000),(3000,8000),(8000,16000))
    for case,row in zip(plan['cases'],fit['cases']):
        folder=a.fit/case['name'];assert row==load(consume(folder/'result.json')) and row['case']==case
        segment=registry['segments'][case['segment']]
        assert case['use'] in segment['allowed_uses'] and segment['source']=='F3'
        with sf.SoundFile(master) as stream:
            assert stream.samplerate==48000 and stream.channels==2 and stream.subtype=='FLOAT'
            first,last=[round(v*48000) for v in case['seconds']];stream.seek(first)
            native=stream.read(last-first,always_2d=True,dtype='float64')
        saved,rate=sf.read(consume(folder/'native.wav'),always_2d=True)
        assert rate==48000 and np.array_equal(native,saved)
        with np.load(consume(folder/'observed.npz')) as f:observed={key:f[key] for key in f.files}
        times,hz=observed['seconds'],observed['hz'];nodes=[];all_peaks=[]
        p_error=b_error=c_error=0.
        for j,start in enumerate(range(0,len(native)-3840+1,240)):
            assert abs(times[j]-(case['seconds'][0]+(start+1920)/48000))<1e-12
            z=np.fft.rfft(native[start:start+3840]*window[:,None],16384,axis=0)
            power=abs(z)**2/(48000*math.fsum(window*window));power[1:-1]*=2
            cross=z[:,0]*z[:,1].conj()/(48000*math.fsum(window*window));cross[1:-1]*=2
            low=power[:len(hz)].mean(axis=1)
            p_error=max(p_error,float(abs(low-observed['power_low'][:,j]).max()))
            for b,(lo,hi) in enumerate(bands):
                keep=(all_hz>=lo)&(all_hz<hi)
                pp=np.array([math.fsum(power[keep,c])*48000/16384 for c in (0,1)])
                b_error=max(b_error,float(abs(pp-observed['power_LR'][:,b,j]).max()))
                c_error=max(c_error,float(abs(sum(cross[keep])*48000/16384-observed['cross_LR'][b,j])))
            found=peaks(hz,low);all_peaks.append(found);values=[]
            for f,prominence in found:
                root=f/5
                if not 20<=root<=90:continue
                support=[]
                for multiple in (2,3,7):
                    distance,prom=min((abs(v-multiple*root),q) for v,q in found)
                    support.append(min(prom,40)/40 if distance<=max(6,.025*multiple*root) else 0.)
                values.append(dict(root=root,score=min(prominence,40)/40+sum(support)))
            nodes.append(values)
        assert max(p_error,b_error,c_error)<1e-12 and len(nodes)==len(times)==145
        selected=min(range(len(times)),key=lambda j:abs(times[j]-case['anchor_seconds']))
        candidates=sorted([(v,q) for v,q in all_peaks[selected] if 100<=v<=450],key=lambda pair:(-pair[1],pair[0]))
        assert abs(candidates[0][0]/5-row['anchor']['root_hz'])<1e-10
        trace=path(nodes,times,candidates[0][0]/5,32)
        assert row['family']['status']=='connected_observed_family'
        root_error=max(abs(nodes[j][k]['root']-expected['root_hz']) for j,(k,expected) in enumerate(zip(trace,row['family']['rows'])))
        assert root_error<1e-10
        with np.load(consume(folder/'coordinates.npz')) as f:positions=f['source_seconds']
        recomputed,cutoff,root=coordinates(native,case['seconds'][0],row['family']['rows'],case['center_seconds'],plan)
        coord_error=float(abs(positions-recomputed).max());assert coord_error<1e-10
        assert abs(cutoff-row['extraction']['phase']['source_cutoff_hz'])<1e-8
        assert abs(root-row['extraction']['root_hz'])<1e-5
        normalized,rate=sf.read(consume(folder/'normalized.wav'),always_2d=True)
        exact=rebuild(native,case['seconds'][0],positions,cutoff)
        assert rate==48000 and np.array_equal(exact.astype('float32').astype(float),normalized)
        coh={str(order):coherence(exact,order).tolist() for order in (3,7)}
        coh_error=max(abs(x-y) for order in coh for x,y in zip(coh[order],row['extraction']['heldout_coherence'][order]))
        assert coh_error<1e-10
        count=len(range(0,len(exact)-4096+1,256))
        qualified=count>=32 and min(v for values in coh.values() for v in values)>.8
        assert count==row['observations'] and qualified==row['qualified']
        result=dict(name=case['name'],frames=len(nodes),direct_power_error_FS2=p_error,
            direct_band_error_FS2=b_error,direct_cross_error_FS2=c_error,path_root_error_hz=root_error,
            inverse_coordinate_error_seconds=coord_error,normalized_FLOAT_exact=True,
            heldout_coherence=coh,coherence_error=coh_error,qualified=qualified)
        if qualified:
            model,model_root=model_load(consume(folder/'voice.model'));h,k=model['basis'].shape[:2]
            assert model_root==row['extraction']['root_hz']
            orders=np.arange(1,h+1);w=.5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
            kernel=np.exp(-2j*np.pi*orders[:,None]*np.arange(4096)[None,:]/1024)*w[None,:]*2/math.fsum(w)
            values=[]
            for start in range(0,len(exact)-4096+1,256):
                z=kernel@exact[start:start+4096]*np.exp(-2j*np.pi*orders*start/1024)[:,None]
                values.append(np.column_stack((z[:,0].real,z[:,0].imag,z[:,1].real,z[:,1].imag)))
            values=np.array(values);centered=values-values.mean(axis=0)
            observed_cov=np.einsum('nhc,nhd->hcd',centered,centered)/(len(values)-1)
            predicted_cov=np.einsum('hkc,hkd->hcd',model['basis'],model['basis'])+np.einsum('hcj,hdj->hcd',model['root'],model['root'])
            mean_error=float(abs(values.mean(axis=0)-model['mean']).max())
            cov_error=float(abs(observed_cov-predicted_cov).max());assert mean_error<1e-10 and cov_error<1e-10
            # Exact deterministic replay checks ALL serialized values, including
            # correlations, but intentionally does not claim independent SVD.
            original,original_positions,_=extract(native,case['seconds'][0],row['family']['rows'],case['center_seconds'],plan)
            assert np.array_equal(original_positions,positions)
            replay,_=estimate(original,288,12);dest=a.out/(case['name']+'_replay.model')
            export(dest,replay,model_root);assert sha(dest)==sha(folder/'voice.model')
            indices=[0,1,239,240,255,256,511,512,4800,11999,47999,95999,191999,383999]
            checks=[];hashes=[]
            for seed in plan['seeds']:
                dest=consume(folder/('DNA_%d.wav'%seed));wave,rate=sf.read(dest,always_2d=True)
                assert wave.shape==(384000,2) and rate==48000 and np.isfinite(wave).all()
                expected=seeded_samples(model,model_root,seed,indices,bandlimited=True)
                check=float_error(wave[indices],expected);check['seed']=seed;checks.append(check);hashes.append(sha(dest))
            assert len(set(hashes))==3
            result.update(root_hz=model_root,model_mean_error_FS=mean_error,all_harmonic_marginal_covariance_error_FS2=cov_error,
                serialized_model_replay_exact=True,replayed_SVD_independent=False,seeded_C_sparse_checks=checks,
                legacy_training_root_boundary_exceeded=model_root>21600/(288*1.1))
        else:assert not (folder/'voice.model').exists() and not list(folder.glob('DNA_*.wav'))
        r['cases'].append(result);save(a.out/'report.json',r)
        print('PASS independent audit',case['name'],flush=True)
    for label,count in [('C_files_sha256.json',656),('voice_files_sha256.json',76)]:
        records=load(consume(a.workspace/'baselines/bandlimited_dna_v1/inputs'/label))
        assert len(records)==count and all(sha(repo/n)==h for n,h in records.items())
    r.update(result='fixed_F3_pitch_anchors_audited',native_frames=sum(v['frames'] for v in r['cases']),
        C_H_exact=656,voice_parameters_exact=76,source_gates_unchanged=True,all_serialized_replays_exact=True,
        earlier_tiny_residual_ratio_failure_reclassified=False,new_independent_rho_gate_claim=False,
        sparse_C_points_per_file=14,human_hearing=False,physical_RPM_or_load=False,runtime_changed=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
