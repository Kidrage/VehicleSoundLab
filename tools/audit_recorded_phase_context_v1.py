"""Independent direct carrier, analytic fixture and recorded-context audit.

Does not import the producer mapper, observation, metrics, fixtures or polish.
Independent explicit FIR taps/direct convolution/upfirdn validate the actual
source-time renders; direct real sin/cos sums validate every carrier window.
"""
import argparse
import math
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy.signal import upfirdn
    import soundfile as sf
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',cases=[],inputs={str(a.study/'report.json'):sha(a.study/'report.json')})
    def interp(v,x,y):
        v=np.asarray(v);j=np.clip(np.searchsorted(x,v,side='right')-1,0,len(x)-2)
        assert np.min(v)>=x[0]-1e-12 and np.max(v)<=x[-1]+1e-12
        return y[j]+(v-x[j])/(x[j+1]-x[j])*(y[j+1]-y[j])
    def unwrap(v):
        delta=np.remainder(np.diff(v)+np.pi,2*np.pi)-np.pi
        return np.r_[v[0],v[0]+np.cumsum(delta)]
    def rows(audio,order,first=0):
        starts=np.arange(0,len(audio)-4096+1,256)
        k=np.arange(4096);h=(1-np.cos(2*np.pi*k/4096))/2
        c=np.cos(2*np.pi*order*k/1024)*h;s=-np.sin(2*np.pi*order*k/1024)*h
        z=np.array([(c@audio[j:j+4096]+1j*(s@audio[j:j+4096]))/1024*
                    complex(math.cos(-2*math.pi*order*(j+first)/1024),
                            math.sin(-2*math.pi*order*(j+first)/1024)) for j in starts])
        return starts+first+2048,z
    def taps(length,normalized,beta):
        k=np.arange(length)-(length-1)/2
        h=normalized*np.sinc(normalized*k)*np.i0(beta*np.sqrt(np.maximum(0,1-(2*k/(length-1))**2)))/np.i0(beta)
        return h/math.fsum(h)
    def render(native,source_start,positions,cutoff):
        lo=math.floor((positions[0]-source_start)*48000+1e-6)-4800
        hi=math.ceil((positions[-1]-source_start)*48000-1e-6)+4801
        assert 0<=lo<hi<=len(native)
        h=taps(1025,2*cutoff/48000,12.)
        filtered=np.column_stack([np.convolve(native[lo:hi,c],h,mode='same') for c in (0,1)])
        # Exact resample_poly16/1 kernel, explicit delay removal. Actual4800
        # sample guards place every requested point far beyond padding support.
        g=np.r_[0.,16*taps(321,1/16,8.6)]
        dense=upfirdn(g,filtered,up=16,axis=0)[161:161+16*len(filtered)]
        at=(positions-source_start-lo/48000)*48000*16
        return np.column_stack([interp(at,np.arange(len(dense)),dense[:,c]) for c in (0,1)])
    def analytic(t,spec):
        output=np.zeros((len(t),2))
        for c in (0,1):
            x=t-c*spec['delay']
            q=spec['root']*x+spec['slope']*x*x/2+spec['pm']*np.sin(2*np.pi*.55*x)
            for j,h in enumerate((3,5,7,11,15)):
                amp=(.07,.2,.065,.04,.025)[j]*(spec['right_ratio'] if c else 1)
                amp=amp*(1+spec['am']*np.sin(2*np.pi*(.7+.13*j)*x+.4*j+.7*c))
                if h==5:
                    amp=amp*spec['reference_gain']
                    if spec['gap']:amp=amp*((x<1.88)|(x>2.12))
                phase=2*np.pi*h*q+.13*h+c*spec['right_phase']
                phase=phase+spec['relative_pm']*(j-2)*np.sin(2*np.pi*1.3*x+.2*c)
                output[:,c]+=amp*np.real(np.exp(1j*phase))
        return output
    def binding(path):
        path=Path(path);r['inputs'][str(path)]=sha(path);return path
    try:
        report=load(a.study/'report.json');known=report['result']=='recorded_phase_context_known_measured'
        assert known or report['result']=='recorded_phase_context_real_measured'
        for name,digest in report['sources'].items():
            assert sha(a.study/'exact_sources'/name)==digest
        for name,digest in report.get('inputs',{}).items():assert sha(binding(name))==digest
        for case in report['cases']:
            path=binding(a.study/case['file']);assert sha(path)==case['sha256']
            with np.load(path) as z:d={name:z[name] for name in z.files}
            native=d['native'];start=float(d.get('source_start',0.))
            if known:
                truth=analytic(np.arange(len(native))/48000,case['spec'])
                assert np.max(abs(truth-native))<2e-12
            else:
                original=case['original_bindings']
                with np.load(binding(original['observer_source'])) as z:
                    assert np.array_equal(d['original_audio'],z['audio'])
                    assert np.array_equal(d['original_positions'],z['coordinates'])
                    assert np.array_equal(native,z['native'])
                with np.load(binding(original['scale'])) as z:
                    assert np.array_equal(d['original_scale'],z['scale']) and z['scale'].shape==(288,1)
                selection=load(binding(original['selection']))
                master=binding(a.workspace/selection['provenance']['master'])
                assert sha(master)==selection['provenance']['master_sha256']
                lo,hi=selection['case']['seconds']
                source,rate=sf.read(master,start=round(lo*48000),stop=round(hi*48000),always_2d=True)
                assert rate==48000 and np.array_equal(source,native) and start==lo
                with np.load(binding(original['coordinates'])) as z:
                    assert np.array_equal(d['original_positions'],z['source_seconds'])
            assert np.array_equal(d['audio'][2048:-2048],d['original_audio'])
            assert np.array_equal(d['positions'][2048:-2048],d['original_positions'])
            assert len(d['audio'])==len(d['original_audio'])+4096 and np.min(np.diff(d['positions']))>0
            # Independent observed coarse source-time integration, anchored at
            # the ORIGINAL rounded aperture origin. No truth is used here.
            t=d['source_clock_times'];hz=interp(t,d['clock_times'],d['root_hz'])
            middle=int(np.searchsorted(t,round(d['aperture'][0]*48000)/48000))
            dq=(hz[:-1]+hz[1:])/96000
            q=np.r_[-np.cumsum(dq[:middle][::-1])[::-1],0.,np.cumsum(dq[middle:])]
            assert np.max(abs(q-d['source_clock_phase']))<2e-12
            estimated=interp(d['coarse_indices']/1024,q,t)
            assert np.max(abs(estimated-d['coarse_positions']))<2e-12
            centers,z=rows(d['coarse_audio'],5,int(d['coarse_indices'][0]))
            original_centers,original_z=rows(d['coarse_audio'][4096:-4096],5)
            slots=np.searchsorted(centers,original_centers)
            z[slots]=original_z
            assert np.array_equal(centers,d['observed_centers'])
            carrier_error=float(np.max(abs(z-d['observed_rows'])))
            assert carrier_error<2e-12
            theta=unwrap(np.angle(z[:,0]));correction=(theta-theta[slots[0]])/(10*np.pi)
            old_theta=unwrap(np.angle(original_z[:,0]))
            correction[slots]=(old_theta-old_theta[0])/(10*np.pi)
            assert np.max(abs(correction-d['observed_correction']))<2e-12
            k=d['observed_indices'];phase=k/1024+interp(k,centers,correction)
            assert np.max(abs(phase-d['observed_phase']))<2e-12 and np.min(np.diff(phase))>0
            at=interp(d['sample_indices']/1024,phase,k)
            expected=interp(at,d['coarse_indices'],d['coarse_positions'])
            coordinate_error=float(np.max(abs(expected-d['positions'])))
            assert coordinate_error<2e-12
            vat=interp(d['validation_indices']/1024,phase,k)
            expected_validation=interp(vat,d['coarse_indices'],d['coarse_positions'])
            assert np.max(abs(expected_validation-d['validation_positions']))<2e-12
            cutoff=case['info']['cutoff_hz'];render_error=0.
            original_ticks=np.arange(round(d['aperture'][0]*48000),round(d['aperture'][1]*48000)+1)/48000
            initial_cutoff=min(14000.,.38*1024*float(min(interp(original_ticks,d['clock_times'],d['root_hz']))))
            for name,pos in (('coarse_audio','coarse_positions'),('audio','positions'),('validation_audio','validation_positions')):
                rebuilt=render(native,start,d[pos],cutoff if name!='coarse_audio' else initial_cutoff)
                error=float(np.max(abs(rebuilt-d[name])));render_error=max(error,render_error)
                assert error<2e-12,(name,error)
            inferred=1/(1024*np.diff(d['positions']))
            assert cutoff<=.45*1024*np.min(inferred)
            minimum=1.;all_metrics={}
            first,last=d['sample_indices'][2048],d['sample_indices'][-2049]
            for h in (3,7):
                at,z=rows(d['validation_audio'],h)
                at+=d['validation_indices'][0]
                all_metrics[str(h)]={}
                for name,mask in dict(whole=np.ones(len(at),bool),before=at<first,
                        target=(at>=first)&(at<=last),after=at>last).items():
                    assert np.any(mask)
                    v=z[mask];coherence=abs(v.sum(axis=0))/np.maximum(abs(v).sum(axis=0),1e-300)
                    amp=abs(v).mean(axis=0)
                    expected=case['heldout'][str(h)][name]
                    assert expected['windows']==int(mask.sum())
                    assert np.max(abs(coherence-expected['coherence']))<2e-12
                    assert np.max(abs(amp-expected['mean_amplitude']))<2e-12
                    minimum=min(minimum,float(min(coherence)))
                    all_metrics[str(h)][name]=dict(windows=int(mask.sum()),coherence=coherence.tolist())
            qualified=minimum>(.99 if known else .8)
            summary=dict(label=case['label'],all_original_arrays_bitwise_exact=True,
                direct_carrier_max_error_FS=carrier_error,inverse_coordinate_max_error_seconds=coordinate_error,
                direct_FIR_and_polyphase_render_max_error_FS=render_error,
                minimum_heldout_coherence=minimum,heldout=all_metrics)
            if known:
                spec=case['spec'];x=d['positions']
                true_q=spec['root']*x+spec['slope']*x*x/2+spec['pm']*np.sin(2*np.pi*.55*x)
                cycle_std=float(np.std(true_q-d['sample_indices']/1024))
                exact=analytic(x,spec);wave=float(np.linalg.norm(d['audio']-exact)/np.linalg.norm(exact))
                assert abs(cycle_std-case['cycle_residual_std'])<2e-12
                assert abs(wave-case['analytic_wave_NRMSE'])<2e-12
                qualified=qualified and cycle_std<.002 and wave<.005
                summary.update(known_cycle_std=cycle_std,analytic_wave_NRMSE=wave)
            assert bool(qualified)==case['qualified']
            summary['qualified']=bool(qualified);r['cases'].append(summary)
            print('INDEPENDENT',case['label'],qualified,'render',render_error,flush=True)
        if known:
            assert len(report['cases'])==8 and len(report['rejections'])==7
            by_name={c['label']:c for c in report['cases']};base=by_name['constant']
            with np.load(a.study/base['file']) as z:
                positions=z['coarse_positions'];cutoff=base['info']['cutoff_hz']
            rejections=[]
            for item in report['rejections']:
                if 'file' in item:
                    path=binding(a.study/item['file']);assert sha(path)==item['sha256']
                    with np.load(path) as z:native=z['native']
                    x=render(native,0,positions,cutoff)
                    centers,z=rows(x,5,-4096)
                    rms=np.array([np.sqrt(np.mean(x[s:s+4096,0]**2)) for s in np.arange(0,len(x)-4096+1,256)])
                    minimum=float(np.min(abs(z[:,0])/np.maximum(rms,1e-300)))
                    assert minimum<.02 and item['reason']==item['expected']=='weak_or_missing_reference'
                else:assert item['reason'] and item['qualified']
                rejections.append(dict(label=item['label'],explicit_rejection_verified=True))
            r['rejections']=rejections
        else:assert len(report['cases'])==6
        all_qualified=all(c['qualified'] for c in r['cases'])
        assert all_qualified==report['all_qualified']
        r.update(result='independent_recorded_phase_context_'+('known' if known else 'real')+'_verified',
            all_qualified=all_qualified,pass_count=sum(c['qualified'] for c in r['cases']),
            no_physical_RPM_or_load_or_runtime_or_hearing_qualification=True,
            producer_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__))
        save(a.out/'report.json',r)
    except BaseException as e:
        r.update(result='failed',error=repr(e));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
