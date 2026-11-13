"""Rebuild local models and correspondence without importing their implementations."""
import argparse,json,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--input',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);p.add_argument('--noise',type=Path)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha


def native_inventory(audio,rate,plan):
    n=len(audio);t=np.arange(n)/n;w=.5-.5*np.cos(2*np.pi*t)
    db=10*np.log10(abs(np.fft.rfft(w*audio[:,0]))**2+1e-30)
    candidates=[];i=1
    while i<len(db)-1:
        end=i
        while end<len(db)-1 and db[end+1]==db[i]:end+=1
        if db[i]>db[i-1] and end<len(db)-1 and db[end]>db[end+1]:
            index=(i+end)//2;left=index;right=index
            while left>0 and db[left-1]<=db[index]:left-=1
            while right<len(db)-1 and db[right+1]<=db[index]:right+=1
            prominence=db[index]-max(db[left:index+1].min(),db[index:right+1].min())
            f=index*rate/n
            if prominence>=plan['prominence_db'] and plan['frequency_band_hz'][0]<=f<plan['frequency_band_hz'][1]:candidates.append(index)
        i=end+1
    if candidates:
        floor=max(db[j] for j in candidates)+plan['relative_floor_db']
        candidates=[j for j in candidates if db[j]>=floor]
    return candidates


def reconstruct(audio,window,state,plan):
    n=len(audio);rate=plan['sample_rate'];m=len(window['lines'])
    native=native_inventory(audio,rate,plan)
    assert native==window['inventory']['native_bins']
    if not m:return dict(wave_error=0.,explained_error=0.,optimality_error=0.)
    time=np.arange(n)/rate-n/(2*rate);w=np.sin(np.pi*np.arange(n)/n)/np.sqrt(n)
    params=state['parameters'];right=state['right_coefficients'];left=params[2*m:]
    nominal=np.asarray(window['inventory']['native_frequency_hz'])
    f=nominal+params[:m];q=params[m:2*m];coeff=np.column_stack((left,right))
    stems=[];derivatives=[]
    for k in range(m):
        oscillator=np.exp(2j*np.pi*(f[k]*time+.5*q[k]*time*time))
        z=coeff[k]-1j*coeff[m+k]
        stems.append(np.real(oscillator[:,None]*z))
        derivatives.append(np.real(1j*oscillator*z[0]))
    stems=np.stack(stems,axis=1);wave=stems.sum(axis=1)+coeff[-1];residual=audio-wave
    wave_error=float(max(abs(wave-state['reconstructed']).max(),abs(residual-state['residual']).max()))
    assert wave_error<=2e-11,wave_error
    derivative=np.stack(derivatives,axis=1)
    phase=2*np.pi*(time[:,None]*f+.5*time[:,None]**2*q)
    jac=np.column_stack((derivative*(2*np.pi*time[:,None]),derivative*(np.pi*time[:,None]**2),
        np.cos(phase),np.sin(phase),np.ones(n)))
    gradient=(w[:,None]*jac).T@(w*(wave[:,0]-audio[:,0]))
    lower,upper=state['lower'],state['upper'];v=np.ones_like(params)
    positive=(gradient>0)&np.isfinite(lower);negative=(gradient<0)&np.isfinite(upper)
    v[positive]=params[positive]-lower[positive];v[negative]=upper[negative]-params[negative]
    optimality=float(np.max(abs(gradient*v)))
    optimality_error=abs(optimality-window['optimality'])
    assert optimality_error<=2e-10,(optimality,window['optimality'])
    assert np.all(params>=lower) and np.all(params<=upper)
    cost=float(np.sum((w*(wave[:,0]-audio[:,0]))**2)/2)
    assert abs(cost-window['cost'])<=1e-12,(cost,window['cost'])
    relative=np.linalg.norm(w[:,None]*residual,axis=0)/np.linalg.norm(w[:,None]*audio,axis=0)
    assert abs(relative-window['weighted_relative_residual_LR']).max()<=2e-11
    hann=w*w*n;hz=np.fft.rfftfreq(n,1/rate);zr=np.fft.rfft(residual*hann[:,None],axis=0)
    width=np.asarray(window['frequency_offset_bounds_hz']);explained_error=0.
    for k,row in enumerate(window['lines']):
        assert row['frequency_hz']==float(f[k]) and row['chirp_hz_per_second']==float(q[k])
        assert row['cosine_LR']==coeff[k].tolist() and row['sine_LR']==coeff[m+k].tolist()
        contact=bool(abs(params[k])>=width[k]-1e-7 or abs(q[k])>=plan['maximum_chirp_hz_per_second']-1e-7)
        extent=abs(q[k])*n/(2*rate)+plan['support_padding_hz'];mask=abs(hz-f[k])<=extent
        zl=np.fft.rfft(stems[:,k]*hann[:,None],axis=0)
        power=np.sum(abs((zr+zl)[mask])**2,axis=0);rp=np.sum(abs(zr[mask])**2,axis=0)
        explained=1-np.divide(rp,power,out=np.ones(2),where=power>0)
        explained_error=max(explained_error,float(abs(explained-row['local_explained_fraction_LR']).max()))
        assert contact==row['bound_contact']
        assert row['eligible']==bool(window['success'] and not contact and min(explained)>=plan['minimum_local_explained_fraction'])
    assert explained_error<=2e-10,explained_error
    # The starting coefficients solve their declared observed linear problem.
    initial=state['initial'];initial_phase=2*np.pi*time[:,None]*nominal
    A=np.column_stack((np.cos(initial_phase),np.sin(initial_phase),np.ones(n)))
    initial_gradient=(w[:,None]*A).T@(w*(A@initial[2*m:]-audio[:,0]))
    assert np.max(abs(initial[:2*m]))==0 and np.max(abs(initial_gradient))<=2e-10
    return dict(wave_error=wave_error,explained_error=explained_error,optimality_error=optimality_error)


def check_links(windows,saved,plan):
    frames=saved['frames'];dt=plan['hop']/plan['sample_rate'];next_id=0
    for t,frame in enumerate(frames):
        assert len(frame)==sum(row['eligible'] for row in windows[t]['lines'])
        for node,original in zip(frame,[r for r in windows[t]['lines'] if r['eligible']]):
            assert all(node[key]==value for key,value in original.items())
        accepted={};edges=[]
        if t:
            for i,previous in enumerate(frames[t-1]):
                for j,current in enumerate(frame):
                    df=current['frequency_hz']-previous['frequency_hz']
                    forward=df-dt*previous['chirp_hz_per_second']
                    backward=-df+dt*current['chirp_hz_per_second']
                    dq=current['chirp_hz_per_second']-previous['chirp_hz_per_second']
                    if abs(forward)<=plan['link_prediction_error_hz'] and abs(backward)<=plan['link_prediction_error_hz'] and abs(dq)<=plan['link_chirp_difference_hz_per_second']:
                        edges.append((i,j,forward,backward,dq))
            actual=saved['transitions'][t-1]['edges'];assert len(actual)==len(edges)
            for row,(i,j,fw,bw,dq) in zip(actual,edges):
                assert row['previous']==i and row['current']==j
                assert max(abs(row['forward_error_hz']-fw),abs(row['backward_error_hz']-bw),abs(row['chirp_difference']-dq))<=1e-12
                if sum(e[0]==i for e in edges)==sum(e[1]==j for e in edges)==1:accepted[j]=frames[t-1][i]['track_id']
        for j,node in enumerate(frame):
            if j in accepted:assert node['track_id']==accepted[j] and node['predecessor']=='unique'
            else:
                assert node['track_id']==next_id
                assert node['predecessor']==('ambiguous' if any(e[1]==j for e in edges) else 'none');next_id+=1
    for track in saved['tracks']:
        rows=[r for frame in frames for r in frame if r['track_id']==track['track_id']]
        frequencies=[r['frequency_hz'] for r in rows];rates=[r['chirp_hz_per_second'] for r in rows]
        kind='unresolved'
        if len(rows)>=plan['minimum_classification_windows']:
            if max(abs(q) for q in rates)<=plan['stationary_maximum_chirp_hz_per_second']:kind='locally_stationary'
            elif float(np.median(abs(np.array(rates))))>=plan['moving_minimum_median_chirp_hz_per_second'] and np.ptp(frequencies)>=plan['moving_minimum_frequency_span_hz'] and (all(q>0 for q in rates) or all(q<0 for q in rates)):kind='locally_moving'
        assert track['windows']==[r['window'] for r in rows] and track['frequencies_hz']==frequencies
        assert track['chirps_hz_per_second']==rates and track['classification']==kind


a.out.mkdir(parents=True,exist_ok=False);report=dict(result='running',optimizer_rerun=False)
try:
    (a.out/'executed_audit.py').write_bytes(Path(__file__).read_bytes())
    parent=load(a.input/'report.json');plan=load(a.input/'exact_sources/research/low_chirp_v1_plan.json')
    assert parent['result']=='native_independent_low_chirps_and_conservative_tracks_observed'
    checked=[]
    for spec in plan['real_sources']:
        folder=a.input/spec['id'];windows=load(folder/'windows.json')
        path=a.workspace/'references/analysis/fixed_source_profiles_v1/trial1'/spec['id']/'training.wav'
        assert sha(path)==next(r['input_sha256'] for r in parent['observations'] if r['id']==spec['id'])
        audio,rate=sf.read(path,always_2d=True)
        for i,window in enumerate(windows):
            start=window['start_frame'];state=dict(np.load(folder/f'window{i}.npz'))
            errors=reconstruct(audio[start:start+plan['frames']],window,state,plan)
            checked.append(dict(source=spec['id'],window=i,**errors))
        check_links(windows,load(folder/'correspondence.json'),plan)
    # Independently reconstruct all model-matched known samples at native rate.
    known=np.load(a.input/'known_signals.npz');controls=load(a.input/'controls.json');known_error=0.
    truth_error=0.
    time=np.arange(plan['frames'])/plan['sample_rate']-.25
    recipes=dict(stationary=([75.31],[0],[.2],[.31]),moving=([85.31],[20],[.2],[.31]),
        neighbor=([75.31,84.23],[4,0],[.18,.13],[.31,-.7]),missing_low=([84.23],[0],[.13],[-.7]))
    for case in controls['cases']:
        name=case['id']
        if name not in ('stationary','moving','neighbor','missing_low'):continue
        observed=case['observation'];output=np.tile(observed['DC_LR'],(len(time),1))
        for row in observed['lines']:
            angle=2*np.pi*(row['frequency_hz']*time+.5*row['chirp_hz_per_second']*time*time)
            output+=np.cos(angle)[:,None]*row['cosine_LR']+np.sin(angle)[:,None]*row['sine_LR']
        known_error=max(known_error,float(abs(output-known[name+'_reconstructed']).max()))
        truth=np.zeros_like(output);frequencies,rates,amplitudes,phases=recipes[name]
        for k,(f,q,amp,phase) in enumerate(zip(frequencies,rates,amplitudes,phases)):
            angle=2*np.pi*(f*time+.5*q*time*time)+phase
            truth[:,0]+=amp*np.cos(angle);truth[:,1]+=.67*amp*np.cos(angle+.13*k)
        truth_error=max(truth_error,float(abs(truth-known[name+'_audio']).max()))
        assert native_inventory(known[name+'_audio'],48000,plan)==observed['inventory']['native_bins']
    assert known_error<=2e-11
    mixed=next(row for row in controls['cases'] if row['id']=='moving_plus_fixed')
    check_links(mixed['observations'],mixed['correspondence'],plan)
    t=np.arange(96000)/48000-1.;truth=np.zeros((96000,2))
    f=np.array([61.37,94.71,127.13,175.89,224.47,285.13]);q=np.array([6,0,12,0,18,0])
    for k,(ff,qq,amp,phase) in enumerate(zip(f,q,[.17,.13,.14,.09,.11,.07],[.2,-.5,.8,.4,-.7,1.1])):
        angle=2*np.pi*(ff*t+.5*qq*t*t)+phase
        truth[:,0]+=amp*np.cos(angle);truth[:,1]+=.67*amp*np.cos(angle+.13*k)
    truth_error=max(truth_error,float(abs(truth-known['mixed_audio']).max()))
    assert truth_error<=2e-12,truth_error
    for number,window in enumerate(mixed['observations']):
        center=-.75+number*.25;expected=f+q*center
        assert native_inventory(known['mixed_audio'][number*12000:number*12000+24000],48000,plan)==window['inventory']['native_bins']
        assert max(abs(row['frequency_hz']-ff) for row,ff in zip(window['lines'],expected))<=plan['known_frequency_error_hz']
        assert max(abs(row['chirp_hz_per_second']-qq) for row,qq in zip(window['lines'],q))<=plan['known_chirp_error_hz_per_second']
    noise_audit=None
    if a.noise:
        noise=load(a.noise/'report.json');arrays=dict(np.load(a.noise/'mono_noise.npz'))
        assert noise['parent_sha256']==sha(a.input/'report.json')
        assert np.array_equal(arrays['audio'][:,0],known['noise_audio'][:,0])
        assert np.array_equal(arrays['audio'][:,1],.67*known['noise_audio'][:,0])
        noise_audit=reconstruct(arrays['audio'],noise['observation'],arrays,plan)
        assert sum(row['eligible'] for row in noise['observation']['lines'])==noise['mono_eligible']
        noise_audit['mono_eligible']=noise['mono_eligible']
    report.update(result='native_models_eligibility_and_every_link_rebuilt',windows=len(checked),
        rows=checked,maximum_wave_error=max(r['wave_error'] for r in checked),
        maximum_explained_error=max(r['explained_error'] for r in checked),
        maximum_optimality_error=max(r['optimality_error'] for r in checked),known_sample_error=known_error,
        known_fixture_sample_error=truth_error,mono_noise_audit=noise_audit,
        parent_sha256=sha(a.input/'report.json'),holdout_read=False,
        scope='Independent model/selection/link arithmetic audit, not optimizer globality or listening acceptance')
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',report)
print(json.dumps({key:value for key,value in report.items() if key!='rows'}),flush=True)
