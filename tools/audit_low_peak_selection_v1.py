"""Independent peak-stage, native-periodogram and FFT score reconstruction."""
import argparse,collections,json,math,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from drive_evidence_v1.sources import sha

def load(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def prominence(db,i):
    height=db[i];left=i;right=i
    while left>0 and db[left-1]<=height:left-=1
    while right<len(db)-1 and db[right+1]<=height:right+=1
    return float(height-max(np.min(db[left:i+1]),np.min(db[i:right+1])))

def fft_scores(reference,current,points,settings,band):
    ix=np.flatnonzero((points>=band[0])&(points<band[1]));n=len(ix)
    assert np.all(np.diff(ix)==1)
    a0=reference[ix]-reference[ix].mean(axis=0)
    dot=sum(signal.correlate(current[:,c],a0[:,c],mode='valid',method='fft') for c in range(2))
    prefix=np.vstack((np.zeros((1,2)),np.cumsum(current,axis=0)))
    squared=np.vstack((np.zeros((1,2)),np.cumsum(current*current,axis=0)))
    sums=prefix[n:]-prefix[:-n];squares=squared[n:]-squared[:-n]
    variance=np.sum(squares-sums*sums/n,axis=1)
    variance=np.maximum(0.,variance)
    norm=np.sqrt(np.sum(a0*a0)*variance)
    start=ix[0]+np.arange(settings['minimum_shift'],settings['maximum_shift']+1)
    return np.divide(dot[start],norm[start],out=np.zeros(len(start)),where=norm[start]>1e-20)

def explicit_feature(cells,hz,points):
    interp=np.column_stack([np.interp(points,hz,cells[:,c]) for c in range(2)])
    floor_value=max(float(np.max(cells))*1e-12,np.finfo(float).tiny)
    logged=np.log(np.maximum(interp,floor_value));radius=512
    kernel=np.exp(-.5*(np.arange(-radius,radius+1)/128)**2);kernel/=kernel.sum()
    smooth=np.column_stack([np.convolve(np.pad(logged[:,c],radius,mode='edge'),kernel,mode='valid') for c in range(2)])
    return logged-smooth

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',windows=[],scale_windows=[])
try:
    shutil.copy2(__file__,a.out/'executed_audit.py')
    base=a.workspace/'references/analysis/low_peak_selection_v1'
    p0=load(repo/'research/idle_modal_v1_plan.json');p1=load(repo/'research/low_spectral_scale_v1_plan.json')
    traces=load(base/'observe1/windows.json');matches=load(base/'scale1/windows.json')
    source=a.workspace/'references/analysis/fixed_source_profiles_v1/trial1/A_exterior_low_rev/training.wav'
    audio,rate=sf.read(source,always_2d=True);assert rate==48000
    saved=np.load(base/'scale1/observations.npz');n=24000
    points=125*2**(np.arange(int(np.ceil(1536*np.log2(12000/125)))+1)/1536)
    features=[];max_prom=0.;max_feature=0.;max_cell=0.;max_final=0.
    causes=collections.Counter();raw_rejections=collections.Counter()
    for j,row in enumerate(traces):
        x=audio[j*12000:j*12000+n]
        hz,psd=signal.periodogram(x,rate,window='hann',detrend=False,axis=0)
        cells=psd*rate/n
        max_cell=max(max_cell,float(abs(cells-saved['cells'][j]).max()))
        assert abs(cells-saved['cells'][j]).max()<1e-14
        factor=np.ones(len(hz))*2;factor[0]=factor[-1]=1
        power=np.sum(psd,axis=1)*rate*np.sum(signal.windows.hann(n,sym=False)**2)/factor
        db=10*np.log10(power+1e-30)
        raw=np.flatnonzero((db[1:-1]>db[:-2])&(db[1:-1]>db[2:]))+1
        assert list(raw)==[peak['bin'] for peak in row['raw_peaks']]
        # Greedy priority thinning independently reconstructs scipy distance selection.
        blocked=np.zeros(len(power),dtype=bool);spaced=set();distance=round(p0['peak_spacing_hz']*n/rate)
        for i in raw[np.argsort(db[raw])[::-1]]:
            if not blocked[i]:
                spaced.add(int(i));blocked[max(0,i-distance+1):min(len(power),i+distance)]=True
        chosen=[];raw_by_bin={peak['bin']:peak for peak in row['raw_peaks']}
        for i in raw:
            if hz[i]>=1250:continue
            old=raw_by_bin[int(i)];prom=prominence(db,int(i));max_prom=max(max_prom,abs(prom-old['prominence_db']))
            assert old['passed']['distance']==(int(i) in spaced)
            assert old['passed']['prominence']==(int(i) in spaced and prom>=p0['peak_prominence_db'])
            if int(i) in spaced and prom>=p0['peak_prominence_db'] and 30<=hz[i]<1200:chosen.append(int(i))
        floor=[i for i in chosen if power[i]>=max(power[k] for k in chosen)*10**(-42/10)]
        capped=sorted(floor,key=lambda i:power[i],reverse=True)[:64]
        q=np.log(power+1e-30);frequencies=[]
        for i in capped:
            delta=.5*(q[i-1]-q[i+1])/(q[i-1]-2*q[i]+q[i+1])
            frequencies.append(float((i+np.clip(delta,-.5,.5))*rate/n))
        error=float(abs(np.sort(frequencies)-row['final_frequencies_hz']).max());max_final=max(max_final,error)
        assert error<1e-9
        for anchor in row['anchors']:
            if anchor['status']=='absent':
                causes[anchor['absence_reason']]+=1
                for candidate in anchor['raw_candidates']:raw_rejections[candidate['first_rejection']]+=1
        # Independent explicit Gaussian convolution versus saved whitened feature.
        actual=explicit_feature(cells,hz,points);fe=float(abs(actual-saved['features'][j]).max());max_feature=max(max_feature,fe)
        assert fe<1e-10
        features.append(actual);r['windows'].append(dict(index=j,final_frequency_error_hz=error,feature_error=fe))
    reference=features[p1['reference_window']];maximum_score_error=0.;total_scores=0
    settings=p1['spectral_scale'];shifts=np.arange(settings['minimum_shift'],settings['maximum_shift']+1)
    for j,current in enumerate(features):
        rows=[matches[j]['global_match'],*matches[j]['band_matches']]
        bands=[settings['comparison_hz'],*p1['independent_comparison_bands_hz']];local=[]
        for old,band in zip(rows,bands):
            scores=fft_scores(reference,current,points,settings,band)
            error=float(abs(scores-np.asarray(old['candidate_scores'])).max());maximum_score_error=max(maximum_score_error,error)
            assert error<1e-10,(j,band,error)
            winner=int(np.argmax(scores));shift=int(shifts[winner]);assert shift==old['shift_bins']
            separate=abs(shifts-shift)>settings['other_peak_exclusion_bins']
            margin=float(scores[winner]-scores[separate].max())
            supported=scores[winner]>=.4 and margin>=.025 and winner not in (0,len(scores)-1)
            assert bool(supported)==old['supported']
            local.append((shift,bool(supported)));total_scores+=len(scores)
        supported=all(s for _,s in local) and max(x[0] for x in local[1:])-min(x[0] for x in local[1:])<=8
        assert supported==matches[j]['supported']
        r['scale_windows'].append(dict(index=j,supported=bool(supported),global_shift=local[0][0]))
    # Additional known mixture verifies the interpretation, without re-fitting A.
    layers=np.load(base/'mixture1/known_layers.npz');mixture_report=load(base/'mixture1/report.json')
    assert mixture_report['result']=='known_moving_layer_with_fixed_layer_rejects_whole_scale_rule'
    assert np.array_equal(layers['moving_reference']+layers['fixed'],layers['mixture_reference'])
    assert np.array_equal(layers['moving_current']+layers['fixed'],layers['mixture_current'])
    sample_error=0.;ratio=2**(128/1536)
    for sample in [0,1,123,1279,5000,23999]:
        t=sample/48000
        for name,q in [('moving_reference',1.),('moving_current',ratio)]:
            value=math.fsum(.07*k**-.65*math.cos(2*math.pi*10.613*k*q*t+.173*k) for k in range(3,451))
            sample_error=max(sample_error,abs(value-layers[name][sample,0]))
        count=len(np.arange(1107.3,5000.,37.137))
        value=math.fsum(.04*math.cos(2*math.pi*(1107.3+37.137*k)*t+.37*k) for k in range(count))
        sample_error=max(sample_error,abs(value-layers['fixed'][sample,0]))
    assert sample_error<1e-10
    mixture_checks=[]
    for names,key in [(('moving_reference','moving_current'),'moving_match'),(('mixture_reference','mixture_current'),'mixed_match')]:
        ff=[]
        for name in names:
            hz,psd=signal.periodogram(layers[name],48000,window='hann',detrend=False,axis=0)
            ff.append(explicit_feature(psd*2,hz,points))
        result=mixture_report[key]
        rebuilt=[]
        for old,band in zip([result['global_match'],*result['band_matches']],
            [settings['comparison_hz'],*p1['independent_comparison_bands_hz']]):
            scores=fft_scores(ff[0],ff[1],points,settings,band)
            error=float(abs(scores-np.asarray(old['candidate_scores'])).max())
            assert error<1e-10,(key,band,error)
            maximum_score_error=max(maximum_score_error,error);total_scores+=len(scores)
            winner=int(np.argmax(scores));shift=int(shifts[winner]);assert shift==old['shift_bins']
            separate=abs(shifts-shift)>settings['other_peak_exclusion_bins']
            margin=float(scores[winner]-scores[separate].max())
            supported=bool(scores[winner]>=.4 and margin>=.025 and winner not in (0,len(scores)-1))
            assert supported==old['supported'];rebuilt.append((shift,supported))
        combined=all(s for _,s in rebuilt) and max(q for q,_ in rebuilt[1:])-min(q for q,_ in rebuilt[1:])<=8
        assert combined==result['supported']
        mixture_checks.append(dict(case=key,global_shift=result['global_match']['shift_bins'],
            band_shifts=[q['shift_bins'] for q in result['band_matches']],supported=result['supported']))
    assert mixture_checks[0]['supported'] and not mixture_checks[1]['supported']
    assert max_prom<1e-9
    r.update(result='selection_stages_and_all69156_real_and_mixture_scores_rebuilt',
        maximum_prominence_error_db=max_prom,maximum_final_frequency_error_hz=max_final,
        maximum_native_cell_error=max_cell,maximum_feature_error=max_feature,
        maximum_score_error=maximum_score_error,score_count=total_scores,
        known_layer_scalar_error=sample_error,known_mixture_checks=mixture_checks,
        absent_anchor_window_counts=dict(causes),rejected_raw_maximum_counts=dict(raw_rejections),
        count_units='Absence counts count windows; rejection counts count raw maxima and may be larger.',
        nonreference_qualified_windows=sum(x['supported'] for x in matches if x['window']!=3),
        reference_self_match_is_validation=False,holdout_used=False,new_profile=False,runtime_changed=False,
        observation_report_sha256=sha(base/'observe1/report.json'),scale_report_sha256=sha(base/'scale1/report.json'))
    print(json.dumps(dict(result=r['result'],scores=total_scores,counts=dict(causes),max_score_error=maximum_score_error)),flush=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
