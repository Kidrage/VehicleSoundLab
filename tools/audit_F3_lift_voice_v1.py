"""Audit all local native frames, scalar paths/carriers and explicit-seed C output."""
import argparse
import math
import os
from pathlib import Path
import shutil
import sys

p=argparse.ArgumentParser(description=__doc__)
for key in ('workspace','fit','build','out'):
    p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[key]='2'
import numpy as np
import soundfile as sf
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
from idle_texture_v1.profile import load as model_load
from sustain_osc_v1.oracle import Gaussian

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},inputs={},cases=[])

def consume(path):
    r['inputs'][str(path)]=sha(path);return path

def peaks(hz,power):
    db=10*np.log10(np.maximum(power,1e-30));indices,info=signal.find_peaks(db,prominence=4)
    rows=[]
    for j,k in enumerate(indices):
        if not 35<=hz[k]<1200:continue
        before,middle,after=map(float,db[k-1:k+2]);den=before-2*middle+after
        delta=.5*(before-after)/den if abs(den)>1e-12 else 0
        rows.append((float(hz[k]+max(-.5,min(.5,delta))*48000/16384),float(info['prominences'][j])))
    return rows

def path(nodes,times,initial,cap):
    score=[v['score']-(abs(math.log2(v['root']/initial))/.1)**2
        if abs(math.log2(v['root']/initial))<=.1 else -math.inf for v in nodes[0]]
    links=[]
    for i in range(1,len(nodes)):
        dt=times[i]-times[i-1];current=[];previous=[]
        for v in nodes[i]:
            costs=[]
            for u,s in zip(nodes[i-1],score):
                velocity=math.log2(v['root']/u['root'])/dt
                costs.append(s-.025*velocity**2 if abs(velocity)<=cap else -math.inf)
            j=max(range(len(costs)),key=costs.__getitem__)
            previous.append(j);current.append(costs[j]+v['score'])
        links.append(previous);score=current
    assert any(math.isfinite(s) for s in score)
    trace=[max(range(len(score)),key=score.__getitem__)]
    for link in reversed(links):trace.append(link[trace[-1]])
    return list(reversed(trace))

def carrier(audio,order):
    window=.5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    kernel=window*np.exp(-2j*np.pi*order*np.arange(4096)/1024)*2/math.fsum(window)
    values=np.array([np.sum(audio[start:start+4096]*kernel[:,None],axis=0)*
        np.exp(-2j*np.pi*order*start/1024) for start in range(0,len(audio)-4096+1,256)])
    return abs(values.mean(axis=0))/np.mean(abs(values),axis=0)

def rebuild(native,start,positions,cutoff):
    first=math.floor((positions[0]-start)*48000+1e-6)-4800
    stop=math.ceil((positions[-1]-start)*48000-1e-6)+4801
    taps=signal.firwin(1025,cutoff,fs=48000,window=('kaiser',12))
    filtered=np.column_stack([np.convolve(native[first:stop,c],taps,mode='same') for c in (0,1)])
    dense=signal.resample_poly(filtered,16,1,axis=0,window=('kaiser',8.6),padtype='line')
    at=(positions-start-first/48000)*48000*16
    return np.column_stack([np.interp(at,np.arange(len(dense)),dense[:,c]) for c in (0,1)])

def seeded_samples(model,root,seed,indices):
    # Independent direct trigonometric synthesis at sparse times; no C recurrence.
    h,k=model['basis'].shape[:2];rng=Gaussian(seed)
    pc=np.array([rng.next() for _ in range(k)])
    residual=np.array([rng.next() for _ in range(h*4)]).reshape(h,4)
    def coefficients():
        return np.einsum('hkc,k->hc',model['basis'],pc*np.sqrt(3/(2+model['rho'])))+np.einsum(
            'hcj,hj->hc',model['root'],residual*np.sqrt(3/(2+model['residual_rho']))[:,None])
    def advance():
        nonlocal pc,residual
        pc=model['rho']*pc+np.sqrt(1-model['rho']**2)*np.array([rng.next() for _ in range(k)])
        rho=model['residual_rho'][:,None]
        residual=rho*residual+np.sqrt(1-rho*rho)*np.array([rng.next() for _ in range(h*4)]).reshape(h,4)
    left=coefficients();advance();right=coefficients();fraction=0.;rows=[];selected=set(indices)
    mean=model['mean'][:,::2]+1j*model['mean'][:,1::2]
    units=np.divide(mean,abs(mean),out=np.ones_like(mean),where=abs(mean)>1e-15)
    for n in range(max(indices)+1):
        while fraction>=1:
            fraction-=1;left=right;advance();right=coefficients()
        if n in selected:
            value=model['mean']+left+fraction*(right-left)
            magnitudes=np.hypot(value[:,::2],value[:,1::2])
            oscillator=np.exp(2j*np.pi*(n*root/48000)*np.arange(1,h+1))
            rows.append(np.sum(magnitudes*np.real(units*oscillator[:,None]),axis=0))
        fraction+=root/12000
    return np.array(rows)

try:
    for name in ('tools/audit_F3_lift_voice_v1.py','tools/idle_texture_v1/profile.py',
                 'tools/sustain_osc_v1/oracle.py','tools/research_archive_v1.py'):
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    # Known Fourier power, signed L/R and carrier gates before this source read.
    known_window=.5-.5*np.cos(2*np.pi*np.arange(16384)/16384)
    t=np.arange(16384)/48000
    known=np.column_stack([.2*np.cos(2*np.pi*375*t),.12*np.cos(2*np.pi*375*t+.4)])
    z=np.fft.rfft(known*known_window[:,None],axis=0)
    power=abs(z)**2/(48000*math.fsum(known_window*known_window));power[1:-1]*=2
    cross=z[:,0]*z[:,1].conj()/(48000*math.fsum(known_window*known_window));cross[1:-1]*=2
    error=max(abs(math.fsum(power[:,c])*48000/16384-amp**2/2) for c,amp in enumerate((.2,.12)))
    assert error<1e-14 and abs(sum(cross)*48000/16384-.2*.12/2*np.exp(-.4j))<1e-14
    kt=np.arange(16384)/1024
    kc=np.column_stack([np.cos(2*np.pi*3*kt),.8*np.cos(2*np.pi*3*kt+.2)])
    assert np.max(abs(carrier(kc,3)-1))<1e-14
    r['known_before_source']=dict(power_error_FS2=error,signed_cross=True,carrier=True)
    window=.5-.5*np.cos(2*np.pi*np.arange(3840)/3840)
    fit=load(consume(a.fit/'report.json'));plan=load(consume(repo/'research/F3_lift_voice_v1_plan.json'))
    old=load(consume(a.fit.parent/'fit1/report.json'));build=load(consume(a.build/'report.json'))
    assert fit['result']=='fixed_local_cases_checked' and fit['qualified']==1 and fit['excluded']==2
    assert build['result']=='passed' and build['correction']['old_seed_labels_invalid']
    assert fit['export_protocol']=='vsl.sound-dna-raw-export/1'
    original_plan=load(a.fit.parent/'fit1/exact_sources/research/F3_lift_voice_v1_plan.json')
    for key in ('cases','window_ms','hop','root_bounds_hz','reference_multiple','check_multiples',
                'max_octaves_per_second','aperture_cycles','phase_reference','heldout_orders','harmonics','components','seconds','seeds','gates'):
        assert plan[key]==original_plan[key],key
    for name,digest in fit['sources'].items():assert sha(repo/name)==digest==sha(a.fit/'exact_sources'/name)
    registry=load(consume(a.workspace/'references/segments_v1.json'))
    assert sha(repo/'references/segments_v1.json')==sha(a.workspace/'references/segments_v1.json')
    source=registry['sources']['F3']
    for key in ('raw','master'):assert sha(consume(a.workspace/source[key]))==source[key+'_sha256']
    with sf.SoundFile(a.workspace/source['master']) as stream:
        stream.seek(round(199.5*48000));context=stream.read(6*48000,dtype='float64',always_2d=True)
    saved,rate=sf.read(consume(a.fit/'native_context.wav'),always_2d=True)
    assert rate==48000 and np.array_equal(context,saved)
    fig,axes=plt.subplots(3,2,figsize=(11,8),layout='constrained')
    bands=((28,120),(120,400),(400,1200),(1200,3000),(3000,8000),(8000,16000))
    all_hz=np.arange(8193)*48000/16384
    total=0
    for i,case in enumerate(plan['cases']):
        folder=a.fit/case['name'];row=fit['cases'][i];before=old['cases'][i]
        lo,hi=[round((s-199.5)*48000) for s in case['seconds']];native=context[lo:hi]
        saved,rate=sf.read(consume(folder/'native.wav'),always_2d=True)
        assert rate==48000 and np.array_equal(native,saved)
        for key in ('anchor','family','extraction','observations','qualified'):assert row[key]==before[key]
        with np.load(consume(folder/'observed.npz')) as f:observed={k:f[k] for k in f.files}
        times,hz=observed['seconds'],observed['hz'];nodes=[];all_peaks=[]
        maximum_power=maximum_cross=maximum_band=0.
        for j,start in enumerate(range(0,len(native)-3840+1,240)):
            assert abs(times[j]-(case['seconds'][0]+(start+1920)/48000))<1e-12
            z=np.fft.rfft(native[start:start+3840]*window[:,None],16384,axis=0)
            power=abs(z)**2/(48000*math.fsum(window*window));power[1:-1]*=2
            cross=z[:,0]*z[:,1].conj()/(48000*math.fsum(window*window));cross[1:-1]*=2
            low=power[:len(hz)].mean(axis=1)
            maximum_power=max(maximum_power,float(abs(low-observed['power_low'][:,j]).max()))
            for b,(bottom,top) in enumerate(bands):
                keep=(all_hz>=bottom)&(all_hz<top)
                values=np.array([math.fsum(power[keep,c])*48000/16384 for c in (0,1)])
                maximum_band=max(maximum_band,float(abs(values-observed['power_LR'][:,b,j]).max()))
                maximum_cross=max(maximum_cross,float(abs(sum(cross[keep])*48000/16384-observed['cross_LR'][b,j])))
            found=peaks(hz,low);all_peaks.append(found);n=[]
            for f,prominence in found:
                root=f/5
                if not 20<=root<=90:continue
                support=[]
                for multiple in (2,3,7):
                    distance,prom=min((abs(v-multiple*root),q) for v,q in found)
                    support.append(min(prom,40)/40 if distance<=max(6,.025*multiple*root) else 0.)
                n.append(dict(root=root,score=min(prominence,40)/40+sum(support),support=support))
            nodes.append(n)
        assert len(nodes)==len(times)==len(row['family']['rows'])
        assert max(maximum_power,maximum_band,maximum_cross)<1e-12
        anchor_index=min(range(len(times)),key=lambda j:abs(times[j]-case['anchor_seconds']))
        candidates=sorted([(v,q) for v,q in all_peaks[anchor_index] if 100<=v<=450],key=lambda pair:(-pair[1],pair[0]))
        assert abs(candidates[0][0]/5-row['anchor']['root_hz'])<1e-10
        trace=path(nodes,times,candidates[0][0]/5,32)
        root_error=max(abs(nodes[j][k]['root']-expected['root_hz']) for j,(k,expected) in enumerate(zip(trace,row['family']['rows'])))
        assert root_error<1e-10
        normalized,rate=sf.read(consume(folder/'normalized.wav'),always_2d=True)
        with np.load(consume(folder/'coordinates.npz')) as f:positions=f['source_seconds']
        exact_normalized=rebuild(native,case['seconds'][0],positions,row['extraction']['phase']['source_cutoff_hz'])
        reconstruction_error=float(abs(exact_normalized-normalized).max())
        assert np.array_equal(exact_normalized.astype('float32').astype('float64'),normalized)
        inferred=1/(1024*np.diff(positions))
        assert float(np.median(inferred))==row['extraction']['root_hz']
        coherences={str(order):carrier(exact_normalized,order).tolist() for order in (3,7)}
        coherence_error=max(abs(x-y) for order in coherences for x,y in zip(coherences[order],row['extraction']['heldout_coherence'][order]))
        assert coherence_error<1e-10
        qualified=row['observations']>=32 and min(v for values in coherences.values() for v in values)>.8
        assert qualified==row['qualified']
        result=dict(name=case['name'],frames=len(nodes),direct_power_error=maximum_power,
            direct_band_error=maximum_band,direct_cross_error=maximum_cross,path_root_error_hz=root_error,
            normalized_reconstruction_error_FS=reconstruction_error,direct_carrier_error=coherence_error,
            heldout_coherence=coherences,qualified=qualified)
        if qualified:
            model,root=model_load(consume(folder/'voice.model'))
            # Direct demodulation of every fitted harmonic, followed by covariance checks.
            h,k=model['basis'].shape[:2];w=np.hanning(4097)[:-1]
            kernel=np.exp(-2j*np.pi*np.arange(1,h+1)[:,None]*np.arange(4096)[None,:]/1024)*w[None,:]*2/math.fsum(w)
            observed_rows=[]
            for start in range(0,len(exact_normalized)-4096+1,256):
                z=kernel@exact_normalized[start:start+4096]*np.exp(-2j*np.pi*np.arange(1,h+1)*start/1024)[:,None]
                observed_rows.append(np.column_stack([z[:,0].real,z[:,0].imag,z[:,1].real,z[:,1].imag]).ravel())
            values=np.array(observed_rows);centered=values-values.mean(axis=0);flat=model['basis'].transpose(1,0,2).reshape(k,-1)
            mean_error=float(abs(values.mean(axis=0).reshape(h,4)-model['mean']).max());assert mean_error<1e-10
            scores=(centered@flat.T)/np.sum(flat*flat,axis=1)[None,:]
            rho=np.clip(np.sum(scores[1:]*scores[:-1],axis=0)/np.sum(scores[:-1]**2,axis=0),-.95,.95)
            assert abs(rho-model['rho']).max()<1e-9
            residual=(centered-scores@flat).reshape(-1,h,4)
            cov=np.einsum('nhc,nhd->hcd',residual,residual)/(len(values)-1)
            restored=np.einsum('hcj,hdj->hcd',model['root'],model['root'])
            cov_error=float(abs(cov-restored).max());assert cov_error<1e-10
            indices=[0,1,239,240,255,256,511,512,4800,11999,47999,95999,191999,383999]
            errors=[];waves=[]
            for seed in plan['seeds']:
                wave,rate=sf.read(consume(folder/f'DNA_{seed}.wav'),always_2d=True)
                assert wave.shape==(384000,2) and rate==48000 and np.isfinite(wave).all() and abs(wave).max()*.5<.95
                expected=seeded_samples(model,root,seed,indices)
                error=float(abs(wave[indices]-expected).max());assert error<1e-7,error
                errors.append(error);waves.append(wave)
            assert all(not np.array_equal(x,y) for j,x in enumerate(waves) for y in waves[j+1:])
            result.update(model_mean_error=mean_error,residual_covariance_error=cov_error,
                seeded_C_sparse_sample_errors_FS=errors,three_seeds_distinct=True)
        else:
            assert not (folder/'voice.model').exists() and not list(folder.glob('DNA_*.wav'))
        r['cases'].append(result);total+=len(nodes)
        db=10*np.log10(np.maximum(observed['power_low'],1e-30))
        axes[i,0].pcolormesh(times,hz,db,shading='auto',vmin=db.max()-50,vmax=db.max(),cmap='magma',rasterized=True)
        axes[i,0].plot(times,[v['reference_hz'] for v in row['family']['rows']],color='cyan',lw=.8)
        axes[i,0].set(title=case['name'],ylabel='Observed Hz',ylim=(35,650))
        for order in (3,7):axes[i,1].plot((0,1),coherences[str(order)],'o-',label=f'order{order}')
        axes[i,1].axhline(.8,color='red',ls=':');axes[i,1].set(ylim=(0,1.05),xticks=(0,1),xticklabels=('L','R'),ylabel='Carrier coherence')
        axes[i,1].legend();save(a.out/'report.json',r)
    assert total==535
    for filename,count in [('C_files_sha256.json',646),('voice_files_sha256.json',74)]:
        records=load(consume(a.workspace/'baselines/bench_load_ui_v1/inputs'/filename))
        assert len(records)==count and all(sha(repo/n)==h for n,h in records.items())
    fig.savefig(a.out/'diagnostic.png',dpi=130);plt.close(fig)
    r.update(result='passed',frames_checked=total,protected_C_H_exact=646,protected_voice_parameters_exact=74,
        new_offline_C_H=1,source_gates_unchanged=True,original_fit1_preserved=True,
        human_hearing=False,physical_RPM_or_load=False,runtime_changed=False)
except Exception as exc:
    r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print({k:r.get(k) for k in ('result','frames_checked','cases')})
