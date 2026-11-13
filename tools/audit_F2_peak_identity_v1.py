"""Independent union-find graph and complex-wave audit; never resolve real fits."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
args=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import read,sha
from line_motion_v1.identity_controls import controls


def load(path):return json.loads(path.read_text(encoding='utf-8'))


def same(a,b):
    if isinstance(a,dict):
        assert a.keys()==b.keys()
        for k in a:same(a[k],b[k])
    elif isinstance(a,list):
        assert len(a)==len(b)
        for x,y in zip(a,b):same(x,y)
    elif isinstance(a,float):assert abs(a-b)<=1e-9
    else:assert a==b


def graph(previous,current):
    """Enumerate the distance matrix, then union connected vertices, including isolates."""
    old=np.array([x['frequency_Hz'] for x in previous]);new=np.array([x['frequency_Hz'] for x in current])
    matrix=abs(old[:,None]-new[None,:])<=2
    links=np.argwhere(matrix).tolist();n=len(old);parent=list(range(n+len(new)))
    def root(k):
        while parent[k]!=k:k=parent[k]
        return k
    for i,j in links:parent[root(n+j)]=root(i)
    groups={}
    for k in range(len(parent)):groups.setdefault(root(k),[]).append(k)
    groups=[g for g in groups.values() if len(g)>1]
    return links,sorted((tuple(k for k in g if k<n),tuple(k-n for k in g if k>=n)) for g in groups)


def wave(parameters,nominal,t):
    m=len(nominal);f=nominal+parameters[:m];q=parameters[m:2*m]
    z=parameters[2*m:3*m]-1j*parameters[3*m:4*m]
    exponent=np.exp(2j*np.pi*(t[:,None]*f+.5*t[:,None]**2*q));v=exponent*z
    return v.real.sum(axis=1)+parameters[-1],np.column_stack(((2j*np.pi*t[:,None]*v).real,
        (1j*np.pi*t[:,None]**2*v).real,exponent.real,exponent.imag,np.ones(len(t))))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-peak-identity-audit/1',result='running',sources={},real_audio_read=False,
    actual_fits_resolved_again=False,model_exported=False,runtime_changed=False,shared_phase_clock_fit=False)
try:
    root=args.workspace/'references/analysis/F2_peak_identity_v1';actual=load(root/'observe1/report.json')
    prior_path=args.workspace/'references/analysis/F2_local_chirps_v1/observe1/report.json';prior=load(prior_path)
    assert actual['prior_report_sha256']==sha(prior_path)
    assert actual['controls']['passed'];same(controls(),actual['controls'])
    # Nonzero omitted-line residual is checked explicitly in addition to the fit gates.
    assert actual['controls']['six_tone_control']['omitted_component_projection']>0
    statistics=[]
    for ch,saved in enumerate(actual['channels']):
        next_id=0;frames=[];unique=0;ambiguous=0
        for w,row in enumerate(prior['observations']):
            nodes=sorted([dict(frequency_Hz=node['native_bin_Hz'],power=node['power'],cell=cell,rank=rank+1)
                for cell,group in enumerate(row['measured']['candidates']) for rank,node in enumerate(group[ch])],key=lambda n:n['frequency_Hz'])
            inherit={};unresolved=set()
            if w:
                links,groups=graph(frames[-1],nodes);transition=saved['transitions'][w-1]
                assert links==transition['links']
                expected=sorted((tuple(g['previous']),tuple(g['current'])) for g in transition['components'])
                assert groups==expected
                for g in transition['components']:assert g['unique']==(len(g['previous'])==len(g['current'])==1)
                for old,new in groups:
                    if len(old)==len(new)==1:inherit[new[0]]=frames[-1][old[0]]['track_id'];unique+=1
                    else:unresolved.update(new);ambiguous+=1
            built=[]
            for j,node in enumerate(nodes):
                if j in inherit:identity=inherit[j]
                else:identity=next_id;next_id+=1
                built.append(dict(**node,track_id=identity,predecessor='unique' if j in inherit else ('ambiguous' if j in unresolved else 'none')))
            assert built==saved['frames'][w];frames.append(built)
        assert next_id==saved['distinct_observation_tracks']
        statistics.append(dict(channel=ch,unique_components=unique,ambiguous_components=ambiguous,discrete_track_count=next_id))
    numbers=np.load(root/'observe1/counterfactual.npz');assert sha(root/'observe1/counterfactual.npz')==actual['arrays_sha256']
    audio,provenance=read(args.workspace,'F2_tailpipe','fixed_window_spectral_observation');report['real_audio_read']=True
    assert provenance==actual['provenance'] and np.array_equal(numbers['audio'],audio[24000:72000])
    old_arrays=np.load(args.workspace/'references/analysis/F2_local_chirps_v1/observe1/observations.npz')
    assert np.array_equal(old_arrays['audio'],audio)
    t=np.arange(48000)/48000-.5;hann=np.sin(np.pi*np.arange(48000)/48000)**2;weight=hann/48000
    errors=dict(waveform=0.,cost=0.,optimality=0.,residual_projection=0.,initial=0.)
    results=[]
    for ch,item in enumerate(actual['counterfactual']):
        old=prior['observations'][1]['measured']['local_chirp_fit'][ch]
        assert item['original_nominal_Hz']==old['nominal_Hz']
        low=prior['observations'][1]['measured']['candidates'][4][ch]
        assert [(n['native_bin_Hz'],i+1) for i,n in enumerate(low) if n['native_bin_Hz'] in (37,45)]==[(45,1),(37,2)]
        assert item['new_nominal_Hz']==old['nominal_Hz']+[37.]
        assert item['original_at_bound']==old['at_bound'] and item['original_cost']==old['cost']
        projections=[]
        for name,fit in [('before',old),('after',item['fit'])]:
            parameters=np.array(fit['fitted_parameters']);nominal=np.array(fit['nominal_Hz']);m=len(nominal)
            predicted,jac=wave(parameters,nominal,t);residual=predicted-numbers['audio'][:,ch]
            errors['waveform']=max(errors['waveform'],float(abs(predicted-numbers[name][:,ch]).max()))
            cost=float(.5*np.dot(weight,residual**2));errors['cost']=max(errors['cost'],abs(cost-fit['cost']))
            low=np.r_[np.full(m,-.5),np.full(m,-2.),np.full(2*m+1,-np.inf)];high=-low
            assert np.all(parameters>=low) and np.all(parameters<=high)
            bound=(abs(parameters[:m])>=.5-1e-7)|(abs(parameters[m:2*m])>=2-1e-7)
            assert bound.tolist()==fit['at_bound']
            gradient=jac.T@(weight*residual);distance=np.ones(len(parameters))
            for j,g in enumerate(gradient):
                if g<0 and np.isfinite(high[j]):distance[j]=high[j]-parameters[j]
                elif g>0 and np.isfinite(low[j]):distance[j]=parameters[j]-low[j]
            optimality=float(abs(distance*gradient).max());errors['optimality']=max(errors['optimality'],abs(optimality-fit['optimality']))
            projection=float(abs(np.vdot(np.exp(2j*np.pi*37*t),hann*residual))/hann.sum());projections.append(projection)
            errors['residual_projection']=max(errors['residual_projection'],abs(projection-item['residual37_projection_'+name]))
            if name=='after':
                z=np.exp(2j*np.pi*t[:,None]*nominal);design=np.column_stack((z.real,z.imag,np.ones(len(t))))
                initial=np.r_[np.zeros(2*m),np.linalg.lstsq(np.sqrt(weight)[:,None]*design,np.sqrt(weight)*numbers['audio'][:,ch],rcond=None)[0]]
                errors['initial']=max(errors['initial'],float(abs(initial-np.array(fit['initial'])).max()))
        assert abs(item['cost_reduction_fraction']-(1-item['new_cost']/item['original_cost']))<1e-14
        assert item['new_cost']==item['fit']['cost']
        results.append(dict(channel=ch,cost_reduction_percent=100*item['cost_reduction_fraction'],
            residual37_reduction_percent=100*(1-projections[1]/projections[0]),
            main_bound_flags_before=old['at_bound'][:3],main_bound_flags_after=item['fit']['at_bound'][:3],
            added37_bound_flag=item['fit']['at_bound'][-1]))
    assert errors['waveform']<1e-10 and errors['cost']<1e-12 and errors['optimality']<1e-10
    assert errors['residual_projection']<1e-12 and errors['initial']<1e-10
    for file,digest in actual['sources'].items():assert sha(repo/file)==sha(root/'observe1/exact_sources'/file)==digest
    for path in (Path(__file__),repo/'tools/drive_evidence_v1/sources.py',repo/'tools/line_motion_v1/identity_controls.py'):
        relative=path.relative_to(repo);target=args.out/'exact_sources'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target);report['sources'][relative.as_posix()]=sha(path)
    report.update(result='all_graph_edges_ambiguities_and_two_counterfactual_fits_independently_audited',
        actual_report_sha256=sha(root/'observe1/report.json'),prior_report_sha256=sha(prior_path),
        controls_replayed=True,source_samples_exact=True,graph_statistics=statistics,counterfactual=results,errors=errors,
        phase_extracted_real_model_permitted=False,RPM_inferred=False,
        limits=['Graph correspondence does not establish physical component identity or phase continuity',
            '37Hz has an ambiguous predecessor at9..10s; it must not become one uninterrupted track',
            'Adding measured37Hz reduces residual but main112/187Hz chirps still touch original bounds',
            'Selected-window training comparison is exploratory, not heldout or perceptual validation'])
    print(json.dumps({k:report[k] for k in ('result','graph_statistics','counterfactual','errors')}),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
