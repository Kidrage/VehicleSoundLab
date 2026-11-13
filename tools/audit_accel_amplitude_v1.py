"""Independent scalar train laws, native scale, mappings and all six transfers."""
import argparse,math,itertools,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy.signal import periodogram
from research_archive_v1 import load,save,sha


def features(audio,settings):
    n=len(audio);window=np.hanning(n+1)[:-1]
    frequency,density=periodogram(audio,48000,window,detrend=False,axis=0)
    cells=density*(48000/n)
    count=math.ceil(settings['bins_per_octave']*math.log2(settings['grid_stop_hz']/settings['grid_base_hz']))+1
    hz=np.array([settings['grid_base_hz']*2**(i/settings['bins_per_octave']) for i in range(count)])
    floor=max(float(cells.max())*1e-12,np.finfo(float).tiny)
    logged=np.column_stack([np.log(np.maximum(np.interp(hz,frequency,cells[:,c]),floor)) for c in range(2)])
    radius=round(4*settings['whitening_sigma_bins'])
    kernel=np.exp(-.5*(np.arange(-radius,radius+1)/settings['whitening_sigma_bins'])**2);kernel/=kernel.sum()
    smooth=np.column_stack([np.convolve(np.pad(logged[:,c],(radius,radius),mode='edge'),kernel,mode='valid') for c in range(2)])
    return hz,cells,logged-smooth


def scale(left,right,hz,settings):
    indices=[i for i,f in enumerate(hz) if settings['comparison_hz'][0]<=f<settings['comparison_hz'][1]]
    def centered(x,shift):
        mean=[math.fsum(x[i+shift,c] for i in indices)/len(indices) for c in range(2)]
        return [float(x[i+shift,c])-mean[c] for i in indices for c in range(2)]
    u=centered(left,0);scores=[]
    shifts=list(range(settings['minimum_shift'],settings['maximum_shift']+1))
    for shift in shifts:
        v=centered(right,shift);den=math.sqrt(math.fsum(z*z for z in u)*math.fsum(z*z for z in v))
        scores.append(math.fsum(x*y for x,y in zip(u,v))/den if den>1e-20 else 0)
    winner=max(range(len(scores)),key=scores.__getitem__)
    other=max(s for i,s in enumerate(scores) if abs(shifts[i]-shifts[winner])>settings['other_peak_exclusion_bins'])
    margin=scores[winner]-other;edge=winner in [0,len(scores)-1]
    supported=scores[winner]>=settings['minimum_score'] and margin>=settings['minimum_peak_margin'] and not edge
    return scores,shifts[winner],2**(shifts[winner]/settings['bins_per_octave']),margin,supported


def training(rows,k):
    selected=[]
    for row in rows:
        if row['guide_supported']:
            for line in row['lines']:
                if line['reference_index']==k and line['eligible']:selected.append((row['tile'],row['ratio'],line))
    return selected


def train(rows):
    if not rows:return None
    x=[float(np.log(ratio)) for _,ratio,_ in rows];n=len(x)
    if n<3 or max(x)-min(x)<np.log(1.03):return None
    center=math.fsum(x)/n;den=math.fsum((v-center)**2 for v in x);logmean=[];slope=[];rms=[]
    for c in range(2):
        y=[math.log(line['amplitude_LR'][c]) for _,_,line in rows];m=math.fsum(y)/n
        logmean.append(m);slope.append(math.fsum((u-center)*(v-m) for u,v in zip(x,y))/den)
        rms.append(math.sqrt(math.fsum(line['amplitude_LR'][c]**2 for _,_,line in rows)/n))
    return dict(count=n,coordinate_mean=center,coordinate_min=min(x),coordinate_max=max(x),
        log_amplitude_mean_LR=logmean,slope_LR=slope,RMS_amplitude_LR=rms,
        frequency_at_ratio1_hz=float(np.median([line['frequency_hz']/ratio for _,ratio,line in rows])))


def prediction(model,x):
    return dict(RMS=model['RMS_amplitude_LR'],geometric=[math.exp(v) for v in model['log_amplitude_mean_LR']],
        log_linear=[math.exp(m+s*(x-model['coordinate_mean'])) for m,s in zip(model['log_amplitude_mean_LR'],model['slope_LR'])])


def close(x,y,tol=1e-10):
    error=float(abs(np.asarray(x)-np.asarray(y)).max(initial=0));assert error<tol,(error,tol)
    return error


a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
r=dict(result='running',models=0,pairs=[],predicted_rows=0,maximum_score_error=0.,maximum_model_error=0.,maximum_prediction_error=0.)
try:
    report=load(a.input/'report.json');assert report['result']=='all6_cross_passage_amplitude_checks_complete'
    for name,h in report['sources'].items():assert sha(a.input/'exact_sources'/name)==h==sha(repo/name)
    plan=report['plan'];settings=load(repo/'research/accel_material_v1_plan.json')['spectral_scale']
    parent=a.workspace/'baselines/accel_chirp_v1/evidence/observe1';ridge=a.workspace/'baselines/accel_ridges_v1/evidence/observe2'
    rows={};reference={};feats={};models={};hz=None
    for name in plan['segments']:
        path=parent/name/'fits.json';assert sha(path)==report['parent_fits_sha256'][str(path)]
        rows[name]=load(path);source=load(ridge/(name+'.json'));reference[name]=source['evidence']['reference_hz']
        saved=np.load(a.input/(name+'_first.npz'));actual=np.load(ridge/(name+'.npz'))['audio'][:12000]
        assert np.array_equal(saved['audio'],actual)
        hz,cells,feats[name]=features(actual,settings)
        close(cells,saved['cells'],1e-12);close(feats[name],saved['feature'],1e-11)
        stored=load(a.input/(name+'_models.json'));models[name]=[];assert len(stored)==len(reference[name])
        for k,item in enumerate(stored):
            selected=training(rows[name],k);model=train(selected)
            assert item['reference_index']==k and item['training_tiles']==[tile for tile,_,_ in selected]
            assert (model is None)==(item['model'] is None)
            if model is not None:
                for key,value in model.items():r['maximum_model_error']=max(r['maximum_model_error'],close(value,item['model'][key]))
                r['models']+=1
            # Predictions below use ORIGINAL stored coefficients, independently verified.
            models[name].append(item['model'])
    keys=['RMS','geometric','log_linear'];totals=dict(compared=0,linear_better=0,amplitude_pass={key:0 for key in keys},both_pass={key:0 for key in keys})
    expected_pairs=list(itertools.permutations(plan['segments'],2));assert len(report['pairs'])==6
    for source,target in expected_pairs:
        pair=load(a.input/(source+'_to_'+target+'.json'));assert (pair['source'],pair['target'])==(source,target)
        scores,shift,ratio,margin,supported=scale(feats[source],feats[target],hz,settings)
        match=pair['scale_match'];r['maximum_score_error']=max(r['maximum_score_error'],close(scores,match['candidate_scores'],1e-11))
        assert shift==match['shift_bins'] and ratio==match['ratio'] and supported==match['supported'];close(margin,match['peak_margin'])
        graph=pair['association'];edges=[]
        for i,f in enumerate(reference[source]):
            expected=f*ratio;radius=4*(1+ratio)+expected*(math.pow(2,.5/192)-1)
            close(expected,graph['expected_hz'][i]);close(radius,graph['radius_hz'][i])
            edges.append([int(abs(expected-v)<=radius) for v in reference[target]])
        assert edges==graph['edges'];verified_rows=[]
        for k,edge in enumerate(edges):
            near=[j for j,yes in enumerate(edge) if yes]
            unique=len(near)==1 and sum(other[near[0]] for other in edges)==1
            state='unique' if unique else 'ambiguous' if near else 'absent';j=near[0] if unique else None
            assert (state,j)==(graph['state'][k],graph['chosen'][k])
            item=pair['references'][k];model=models[source][k]
            assert item['source_reference']==k and item['association']==state and item['target_reference']==j
            assert item['model_available']==(model is not None)
            status='scale_unsupported' if not supported else 'association_'+state if state!='unique' else 'insufficient_training' if model is None else None
            inrows=[]
            if status is None:
                selected=training(rows[target],j);assert len(selected)==len(item['rows'])
                for (tile,withinratio,line),check in zip(selected,item['rows']):
                    x=float(np.log(ratio*withinratio));inside=model['coordinate_min']<=x<=model['coordinate_max']
                    assert check['tile']==tile and check['within_source_range']==inside;close(x,check['coordinate'])
                    if not inside:assert set(check)=={'tile','coordinate','within_source_range'};continue
                    pred=prediction(model,x);observed=line['amplitude_LR'];close(observed,check['observed_amplitude_LR'])
                    ferr=line['frequency_hz']-model['frequency_at_ratio1_hz']*math.exp(x);close(ferr,check['frequency_error_hz'])
                    errors={key:[20/math.log(10)*(math.log(o)-math.log(v)) for o,v in zip(observed,pred[key])] for key in keys}
                    for key in keys:
                        r['maximum_prediction_error']=max(r['maximum_prediction_error'],close(pred[key],check['predicted_amplitude_LR'][key]),close(errors[key],check['error_db_LR'][key]))
                    inrows.append(check);r['predicted_rows']+=1
                assert len(selected)==item['eligible_target_count'] and len(inrows)==item['within_count']
                status='compared' if len(inrows)>=3 and len(inrows)>=.5*len(selected) else 'insufficient_target_range'
                if status=='compared':
                    for key in keys:
                        error=float(np.median([abs(v) for check in inrows for v in check['error_db_LR'][key]]))
                        close(error,item['median_absolute_error_db'][key])
                        maximum=max(abs(check['frequency_error_hz']) for check in inrows);close(maximum,item['maximum_frequency_error_hz'])
                        assert (error<=3 and maximum<=4)==item['diagnostic_targets_met'][key]
            assert status==item['status'];verified_rows.append(item)
        compared=[row for row in verified_rows if row['status']=='compared']
        window_indices=[]
        for tile in range(len(rows[target])):
            selected=[(row['source_reference'],check) for row in compared for check in row['rows'] if check['tile']==tile and check['within_source_range']]
            if len(selected)<3:continue
            result=pair['window_shape'][len(window_indices)];window_indices.append(tile)
            assert result['tile']==tile and result['source_references']==[k for k,_ in selected]
            for key in keys:
                errors=[check['error_db_LR'][key] for _,check in selected]
                mean=[math.fsum(e[c] for e in errors)/len(errors) for c in range(2)]
                centered=[[e[c]-mean[c] for c in range(2)] for e in errors]
                close(mean,result['common_error_db_LR'][key]);close(centered,result['centered_error_db_LR'][key])
        assert len(window_indices)==len(pair['window_shape'])
        summary=pair['summary'];assert summary['compared']==len(compared)
        assert summary['unique_associations']==graph['state'].count('unique') and summary['scale_supported']==supported
        assert summary['status_counts']=={s:sum(row['status']==s for row in verified_rows) for s in sorted({row['status'] for row in verified_rows})}
        for key in keys:
            close(np.median([row['median_absolute_error_db'][key] for row in compared]),summary['median_reference_error_db'][key])
            amp=sum(row['median_absolute_error_db'][key]<=3 for row in compared);both=sum(row['diagnostic_targets_met'][key] for row in compared)
            assert amp==summary['amplitude3dB_pass'][key] and both==summary['both_diagnostics_pass'][key]
            totals['amplitude_pass'][key]+=amp;totals['both_pass'][key]+=both
        better=sum(row['median_absolute_error_db']['log_linear']<row['median_absolute_error_db']['geometric'] for row in compared)
        assert better==summary['log_linear_better_than_geometric'];totals['linear_better']+=better;totals['compared']+=len(compared)
        published=next(v for v in report['pairs'] if (v['source'],v['target'])==(source,target))
        assert published==dict(source=source,target=target,**summary)
        r['pairs'].append(published)
    baseline=a.workspace/'baselines/idle_microtexture_c_v1/inputs'
    for filename,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
        invariant=load(baseline/filename);assert len(invariant)==count
        for name,h in invariant.items():assert sha(repo/name)==h,name
    r.update(result='all_source_models_native_matches_and6_transfer_reports_verified',totals=totals,
        input_report_sha256=sha(a.input/'report.json'),C_H_unchanged=612,old_voices_unchanged=67,
        target_amplitude_training=False,source_identity_or_RPM_load=False,pristine_holdout=False,
        conclusion='Log-linear acoustic-scale amplitude is not consistently better than geometric constant; no sound/profile export.')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print({key:r[key] for key in ['result','models','predicted_rows','totals','maximum_model_error','maximum_prediction_error','maximum_score_error']},flush=True)
