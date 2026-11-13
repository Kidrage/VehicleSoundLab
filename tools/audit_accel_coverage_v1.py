"""Independent complex OSC and scalar native spectral-power/interference audit."""
import argparse,math,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy.fft import rfft
from research_archive_v1 import load,save,sha


def powers(x,y,bands):
    n=len(x);w=np.array([.5-.5*math.cos(2*math.pi*i/n) for i in range(n)])
    X=rfft(x*w[:,None],axis=0);Y=rfft(y*w[:,None],axis=0);R=X-Y
    weight=np.array([1. if i in [0,n//2] else 2. for i in range(n//2+1)])/(n*math.fsum(w*w))
    arrays=dict(source=X.real**2+X.imag**2,model=Y.real**2+Y.imag**2,
        residual=R.real**2+R.imag**2,interference=2*(Y.real*R.real+Y.imag*R.imag))
    return {key:np.array([[math.fsum(float(value[i,c])*weight[i] for i in range(len(weight)) if lo<=i*4<hi)
        for c in range(2)] for lo,hi in bands]) for key,value in arrays.items()}


def close(x,y,tol=1e-12):
    error=float(abs(np.asarray(x)-np.asarray(y)).max(initial=0));assert error<tol,(error,tol)
    return error


a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
r=dict(result='running',tiles=0,maximum_waveform_error=0.,maximum_power_error=0.,maximum_identity_error=0.)
try:
    original=load(a.input/'report.json');assert original['result']=='all48_native_coverage_with_interference_observed'
    for name,h in original['sources'].items():assert sha(a.input/'exact_sources'/name)==h==sha(repo/name)
    plan=original['plan'];parent=a.workspace/'baselines/accel_chirp_v1/evidence/observe1';n=12000
    t=(np.arange(n)-n/2)/48000;summary=[]
    for name in plan['segments']:
        source=load(a.input/name/'report.json');path=parent/name/'fits.json';assert sha(path)==source['parent_fits_sha256']
        fits=load(path);assert len(fits)==len(source['rows']);recomputed=[]
        for i,(fit,entry) in enumerate(zip(fits,source['rows'])):
            parent_tile=parent/name/f'tile_{i:02d}.npz';saved=np.load(a.input/name/f'tile_{i:02d}.npz')
            assert sha(parent_tile)==entry['parent_sha256'];native=np.load(parent_tile)
            assert np.array_equal(native['audio'],saved['audio']) and entry['tile']==i
            assert entry['fit_success']==fit['success'] and entry['guide_supported']==fit['guide_supported']
            assert entry['all_lines']==len(fit['lines']) and entry['eligible_lines']==sum(line['eligible'] for line in fit['lines'])
            close(entry['frequency_min_hz'],min(line['frequency_hz'] for line in fit['lines']))
            close(entry['frequency_max_hz'],max(line['frequency_hz'] for line in fit['lines']))
            pair={}
            for eligible,field in [(False,'all'),(True,'eligible')]:
                y=np.tile(fit['DC_LR'],(n,1)).astype(float)
                for line in fit['lines']:
                    if eligible and not line['eligible']:continue
                    phase=2*np.pi*(line['frequency_hz']*t+.5*line['chirp_hz_per_second']*t*t)
                    coefficient=np.asarray(line['cosine_LR'])-1j*np.asarray(line['sine_LR'])
                    y+=(np.exp(1j*phase)[:,None]*coefficient).real
                r['maximum_waveform_error']=max(r['maximum_waveform_error'],close(y,saved[field+'_model']))
                if not eligible:close(y,native['reconstructed'])
                measured=powers(saved['audio'],y,plan['bands_hz'])
                for key,value in measured.items():r['maximum_power_error']=max(r['maximum_power_error'],close(value,entry[field+'_parts'][key]))
                error=close(measured['source'],measured['model']+measured['residual']+measured['interference'])
                r['maximum_identity_error']=max(r['maximum_identity_error'],error);pair[field+'_parts']=measured
            recomputed.append(pair);r['tiles']+=1
        for kind in ['all_parts','eligible_parts']:
            summed={key:np.sum([row[kind][key] for row in recomputed],axis=0) for key in ['source','model','residual','interference']}
            expected=source['aggregate'][kind]
            for key,value in summed.items():close(value,expected['powers'][key])
            close(summed['source']/summed['source'].sum(axis=0),expected['source_fraction'])
            for field,key in [('model_over_source','model'),('residual_over_source','residual'),('cross_over_source','interference')]:
                close(summed[key]/summed['source'],expected[field])
        published=next(row for row in original['observations'] if row['segment']==name)
        assert published=={key:source[key] for key in ['segment','tiles','aggregate']}
        summary.append(dict(segment=name,frequency_range=[min(v['frequency_min_hz'] for v in source['rows']),max(v['frequency_max_hz'] for v in source['rows'])],
            failed_fits=sum(not v['fit_success'] for v in source['rows']),guide_failures=sum(not v['guide_supported'] for v in source['rows'])))
    # Rebuild native known controls without the observation implementation.
    amplitudes=np.array([.3,.2,.15,.1,.07,.04,.02]);freq=[80,220,600,1600,3000,6000,10000]
    signal=sum(amp*np.cos(2*np.pi*f*np.arange(n)/48000) for amp,f in zip(amplitudes,freq))
    x=np.column_stack((signal,.7*signal));controls=load(a.input/'controls.json')
    absent=x-amplitudes[-1]*np.cos(2*np.pi*freq[-1]*np.arange(n)/48000)[:,None]*np.array([[1.,.7]])
    for tag,y in [('exact',x),('missing',absent),('destructive',x*1.5)]:
        for key,value in powers(x,y,plan['bands_hz']).items():close(value,controls[tag][key])
    invariants=a.workspace/'baselines/idle_microtexture_c_v1/inputs'
    for filename,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
        table=load(invariants/filename);assert len(table)==count
        for name,h in table.items():assert sha(repo/name)==h,name
    r.update(result='all48_native_models_band_powers_and_signed_interference_verified',summaries=summary,
        input_report_sha256=sha(a.input/'report.json'),C_H_unchanged=612,old_voices_unchanged=67,
        residual_physical_noise=False,source_or_RPM_load_identity=False,source_chirplet_run=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r,flush=True)
