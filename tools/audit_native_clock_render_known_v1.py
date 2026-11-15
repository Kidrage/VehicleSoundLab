"""Independent clock/basis/FIR/native-reference audit; no producer imports."""
import argparse
import bisect
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import signal
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',cases=[],inputs={},maximum_errors={})
    def check(name,x,y,scale,gate):
        x,y=np.asarray(x),np.asarray(y);assert x.shape==y.shape,(name,x.shape,y.shape)
        if scale==0:
            assert np.count_nonzero(x)==np.count_nonzero(y)==0;error=0.
        else:error=float(np.max(abs(x-y))/scale)
        r['maximum_errors'][name]=max(error,r['maximum_errors'].get(name,0.))
        assert error<=gate,(name,error,gate)
        return error
    def kernel(up):
        length=256*up+1;mid=length//2;rate=48000*up
        ix=np.arange(-mid,mid+1,dtype=float)
        base=np.array([2*22000/rate if k==0 else math.sin(2*math.pi*22000*k/rate)/(math.pi*k) for k in ix])
        window=np.i0(12*np.sqrt(np.maximum(0,1-(ix/mid)**2)))/np.i0(12)
        taps=base*window
        return taps/math.fsum(taps)
    def phase(t,s):
        return s['root']*t+s['slope']*t*t/2+s['cubic']*t*t*t/3+s['pm']*np.sin((1.6*np.pi)*t)
    def active(label):
        return (range(1,289) if label=='full288' else [152,160,172,184,192,219] if label=='near_Nyquist'
            else [203] if label=='pure_stopband' else [3,5,7,71,127,193,249])
    def physical(times,s,label,center):
        p=phase(times,s);pd=phase(times-s['delay'],s)
        output=np.zeros((len(times),2))
        for i,h in enumerate(active(label)):
            amplitude=.07/(1+.02*h) if label=='full288' else .09/(1+.4*i)
            if s['zero']:amplitude=0.
            left=2*np.pi*np.remainder(h*p,1)+.13*h
            right=2*np.pi*np.remainder(h*pd,1)+.13*h+.37
            output[:,0]+=amplitude*(1+s['am']*(p-center))*np.cos(left)
            output[:,1]+=.61*amplitude*(1-.75*s['am']*(p-center))*np.cos(right)
        if s['mono']:output[:,1]=output[:,0]
        if s['silent']:output[:,1]=0
        return output
    try:
        source=load(a.study/'report.json')
        assert source['result']=='native_clock_render_known_measured'
        labels=['zero','mono','unequal_phase','silent_right','linear_AM','rising_clock','falling_clock',
            'common_PM','delayed_right','cubic_chirp','near_Nyquist','pure_stopband','full288']
        assert [c['label'] for c in source['cases']]==labels
        r['inputs'][str(a.study/'report.json')]=sha(a.study/'report.json')
        for name,digest in source['sources'].items():assert sha(a.study/'exact_sources'/name)==digest
        plan=load(a.study/'exact_sources/research/native_clock_render_v1_plan.json');g=plan['gates']
        filters={up:kernel(up) for up in (16,32)}
        for up,taps in filters.items():
            assert abs(math.fsum(taps)-1)<=g['FIR_DC_error_max']
            assert np.array_equal(taps,taps[::-1])
            f,h=signal.freqz(taps,worN=524288,fs=48000*up)
            edge,edge_h=signal.freqz(taps,worN=np.array([20000.,24000.,24000.*up]),fs=48000*up)
            f,h=np.r_[f,edge],np.r_[h,edge_h]
            assert np.max(abs(20*np.log10(abs(h[f<=20000]))))<=g['FIR_passband_0_to_20000_max_dB']
            assert np.max(abs(h[f>=24000]))<=g['FIR_stopband_24000_to_denseNyquist_max_magnitude']
        for c in source['cases']:
            path=a.study/c['file'];assert sha(path)==c['sha256'];r['inputs'][str(path)]=sha(path)
            with np.load(path) as f:z={k:f[k] for k in f.files}
            s=c['spec'];label=c['label'];count=int(z['count']);up=16;delay=2048
            assert np.array_equal(z['orders'],np.arange(1,289)) and z['nodes'].shape==(len(z['positions']),288,2)
            assert z['positions'][0]==0 and z['positions'][-1]==len(z['source_seconds'])-1
            assert np.all(np.diff(z['source_seconds'])>0) and np.all(np.diff(z['positions'])>0)
            assert len(np.unique(np.diff(z['positions'])))>1
            check('explicit_Kaiser_FIR',z['taps'],filters[16],float(np.max(abs(filters[16]))),2e-11)
            scale=float(np.max(np.sum(abs(z['nodes']),axis=1)))
            relative=z['source_seconds']-z['source_seconds'][0]
            selected=np.unique(np.linspace(0,len(z['query'])-1,37,dtype=int))
            query=[];expected=[]
            for k in selected:
                time=float(z['native_start'])-z['source_seconds'][0]+(int(k)-delay)/(48000*up)
                assert relative[0]<=time<=relative[-1]
                j=min(bisect.bisect_right(relative,time)-1,len(relative)-2)
                u=j+(time-relative[j])/(relative[j+1]-relative[j]);query.append(u)
                slot=min(bisect.bisect_right(z['positions'],u)-1,len(z['positions'])-2)
                fraction=(u-z['positions'][slot])/(z['positions'][slot+1]-z['positions'][slot])
                values=[]
                for channel in (0,1):
                    terms=[]
                    for h in range(1,289):
                        a0=z['nodes'][slot,h-1,channel];a1=z['nodes'][slot+1,h-1,channel]
                        value=a0+(a1-a0)*fraction
                        angle=2*math.pi*math.remainder(h*u/1024,1)
                        terms.append(value.real*math.cos(angle)-value.imag*math.sin(angle))
                    values.append(math.fsum(terms))
                expected.append(values)
            check('scalar_inverse_phase',z['query'][selected]/1024,np.array(query)/1024,1.,2e-11)
            check('scalar_all288_continuous_basis',z['dense_wave'][selected],np.array(expected),scale,
                g['scalar_continuous_basis_relative_to_coefficient_L1_max'])
            # Independent original integer-cycle Fourier convention, all288
            # orders and original nonuniform hats, not the continuous renderer.
            probes=z['integer_probe_indices'];integer=np.zeros((len(probes),2))
            for node,position in enumerate(z['positions']):
                bins=np.zeros((1024,2),complex)
                bins[1:289]=z['nodes'][node]/2
                bins[-np.arange(1,289)]=z['nodes'][node].conj()/2
                cycle=(np.fft.ifft(bins,axis=0)*1024).real
                left=z['positions'][node-1] if node else position
                right=z['positions'][node+1] if node+1<len(z['positions']) else position
                hats=np.zeros(len(probes))
                if node:
                    ids=(probes>=left)&(probes<=position);hats[ids]=(probes[ids]-left)/(position-left)
                if node+1<len(z['positions']):
                    ids=(probes>=position)&(probes<=right);hats[ids]=(right-probes[ids])/(right-position)
                integer+=hats[:,None]*cycle[probes%1024]
            check('original_integer_cycle_model',z['integer_probe_wave'],integer,scale,2e-11)
            native_indices=np.unique(np.linspace(0,count-1,33,dtype=int))
            direct=np.array([filters[16][::-1]@z['dense_wave'][k*up:k*up+len(filters[16])] for k in native_indices])
            check('independent_direct_FIR_outputs',z['native'][native_indices],direct,scale,
                g['independent_same_dense_direct_FIR_relative_source_amplitude_max'])
            assert z['native'].shape==(count,2)
            # New32x physical-time analytic source, independent of the saved
            # phase interpolation and coefficient trajectories.
            high_up=32;high_delay=4096
            ticks=np.arange(-high_delay,(count-1)*high_up+high_delay+1)
            time=float(z['native_start'])-17+ticks/(48000*high_up)
            truth=physical(time,s,label,float(z['center']))
            filtered=signal.upfirdn(filters[32],truth,down=high_up,axis=0)
            reference=filtered[(len(filters[32])-1)//high_up:][:count]
            delta=z['native']-reference
            denominator=float(np.linalg.norm(reference))
            error=float(np.linalg.norm(delta)/denominator) if denominator else (0. if not np.count_nonzero(delta) else None)
            if s['zero']:assert np.count_nonzero(delta)==0
            elif label=='pure_stopband':
                attenuation=float(np.max(abs(z['native']))/np.max(abs(truth)))
                assert attenuation<=g['pure_stopband_native_peak_relative_to_source_peak_max']
            else:assert error is not None and error<=g['native16x_vs_analytic32x_reference_NRMSE_max'],(label,error)
            stationary=not any(s[k] for k in ('slope','cubic','pm','am','delay'))
            closed_error=None
            if stationary:
                t=float(z['native_start'])-17+np.arange(count)/48000
                closed=np.zeros((count,2));indices=np.arange(-delay,delay+1)
                for i,h in enumerate(active(label)):
                    amplitude=.07/(1+.02*h) if label=='full288' else .09/(1+.4*i)
                    if s['zero']:amplitude=0.
                    gain=math.fsum(filters[16]*np.cos(2*np.pi*h*s['root']*indices/(48000*up)))
                    closed[:,0]+=amplitude*gain*np.cos(2*np.pi*np.remainder(h*s['root']*t,1)+.13*h)
                    closed[:,1]+=.61*amplitude*gain*np.cos(2*np.pi*np.remainder(h*s['root']*t,1)+.13*h+.37)
                if s['mono']:closed[:,1]=closed[:,0]
                if s['silent']:closed[:,1]=0
                closed_error=check('stationary_closed_form_filtered_harmonics',z['native'],closed,scale,
                    g['stationary_native_vs_closed_form_filtered_harmonics_relative_source_max'])
            if s['mono']:assert np.count_nonzero(z['native'][:,0]-z['native'][:,1])==0
            if s['silent']:assert np.count_nonzero(z['native'][:,1])==0
            output=a.out/(label+'.npz');np.savez_compressed(output,reference32=reference,signed_native_error=delta,
                scalar_query_indices=selected,scalar_query=np.array(query),scalar_basis=np.array(expected),
                direct_FIR_indices=native_indices,direct_FIR=direct)
            r['cases'].append(dict(label=label,all_known_gates_passed=True,native32_reference_NRMSE=error,
                stationary_closed_form_error=closed_error,signed_native_mean_error=delta.mean(axis=0).tolist(),
                signed_native_peak_range=[delta.min(axis=0).tolist(),delta.max(axis=0).tolist()],
                original_all288_orders_and_nodes_preserved=True,reference_file=output.name,reference_sha256=sha(output)))
            save(a.out/'report.json',r);print('NATIVE_CLOCK_AUDIT',label,'PASS32x',error,flush=True)
        assert len(source['guards'])==10
        assert all(c['all_known_gates_passed'] for c in r['cases'])
        r.update(result='independent_native_clock_render_known_verified',all_known_qualified=True,
            producer_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__),
            real_fit_or_universal_oversampling_or_C_or_hearing_qualified=False)
        save(a.out/'report.json',r)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
