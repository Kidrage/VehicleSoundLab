"""Known full-present/deleted verification and explicit native/augmented adoption."""
import argparse
import shutil
import sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy.linalg import lstsq
from research_archive_v1 import load,save,sha
from native_phase_patch_v1.fit import fit
from native_phase_patch_v1.basis import projection
from native_phase_patch_v1.link import link
from native_phase_patch_v1.score import score
from accel_low_fit_v1.observe import temporal
from candidate_presence_v1.propose import propose
from candidate_presence_v1.presence import accept
from candidate_prediction_v1.fit import fit as fit_verification
from candidate_prediction_v1.decision import decide

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},parent_files={},summaries=[],real_source_read=False,
    prerequisite_passed=False,planned_windows=108,executed_windows=0)
baseline=a.workspace/'baselines/candidate_presence_v1'
parent_root=baseline/'evidence/observe1'
table={v['path']:v['sha256'] for v in load(baseline/'manifest.json')['files']}


def parent(path):
    name=path.relative_to(baseline).as_posix()
    h=sha(path)
    assert table[name]==h
    r['parent_files'][name]=h
    return path


def run(case):
    source=parent_root/case
    folder=a.out/case
    folder.mkdir()
    audio=np.load(parent(source/'signal.npz'))['audio']
    observed=load(parent(source/'initialization.json'))
    native=load(parent(source/'native_fits.json'))
    shutil.copy2(source/'signal.npz',folder/'signal.npz')
    save(folder/'initialization.json',observed)
    save(folder/'native_fits.json',native)
    rows,raws,postfits,proposals,presences,verifications,decisions=[],[],[],[],[],[],[]
    for i,(inv,base) in enumerate(zip(observed['inventories'],native)):
        tile=audio[i*12000:(i+1)*12000]
        with np.load(parent(source/f'native_{i:02d}.npz')) as loaded:
            native_z={k:loaded[k] for k in loaded.files if k!='audio'}
        previous=rows[-1] if rows else None
        proposal=propose(inv,observed['initial'][i],previous)
        nominal=np.array(proposal['inventory']['bin'])*4
        chirp=np.array(proposal['initial_chirp'])
        if proposal['added_bins']:
            raw,z=fit(tile,nominal,chirp,fp)
            train,tz=fit_verification(tile,nominal,chirp,fp)
            np.savez_compressed(folder/f'verify_present_{i:02d}.npz',audio=tile,**tz)
            deleted={}
            for cell in proposal['added_bins']:
                keep=np.array([v!=cell for v in proposal['inventory']['bin']])
                deleted[cell],dz=fit_verification(tile,nominal[keep],chirp[keep],fp)
                np.savez_compressed(folder/f'verify_deleted_{i:02d}_{cell:04d}.npz',audio=tile,**dz)
        else:
            raw,z=base,native_z
            train,deleted=None,{}
        postfit,presence=accept(raw,z,tile,proposal,previous)
        chosen,decision=decide(base,raw,postfit,proposal,train,deleted)
        selected_z=z if decision['augmented_adopted'] else native_z
        rows.append(chosen)
        raws.append(raw)
        postfits.append(postfit)
        proposals.append(proposal)
        presences.append(presence)
        verifications.append(dict(present=train,deleted=deleted))
        decisions.append(decision)
        np.savez_compressed(folder/f'tile_{i:02d}.npz',audio=tile,**z)
        np.savez_compressed(folder/f'selected_{i:02d}.npz',audio=tile,**selected_z)
        for name,value in [('raw_fits',raws),('augmented_accepted_fits',postfits),('fits',rows),
            ('proposals',proposals),('presence',presences),('verification_fits',verifications),('decisions',decisions)]:save(folder/(name+'.json'),value)
        r['executed_windows']+=1
        save(a.out/'report.json',r)
        print(dict(case=case,window=i,added=proposal['added_bins'],full_success=raw['success'],
            verification_success=train['success'] if train else None,decision=decision['reason'],
            selected_modes=len(chosen['lines']),selected_eligible=sum(v['eligible'] for v in chosen['lines'])),flush=True)
    old=load(parent(source/'links.json'))
    links=dict(native_old=old['native_old'],native_boundary=old['native_boundary'],
        unscreened_old=old['augmented_old'],unscreened_boundary=old['augmented_boundary'],
        selected_old=temporal(rows,lp),selected_boundary=link(rows,lp))
    if 'previous_old' in old:links.update(previous_old=old['previous_old'],previous_boundary=old['previous_boundary'])
    save(folder/'links.json',links)
    return rows,links


def finish(case,rows,links):
    truth=load(parent(parent_root/case/'truth.json'))
    save(a.out/case/'truth.json',truth)
    scores={key:score(value,truth['rows']) for key,value in links.items()}
    save(a.out/case/'scores.json',scores)
    decisions=load(a.out/case/'decisions.json')
    r['summaries'].append(dict(case=case,windows=len(rows),successful=sum(v['success'] for v in rows),
        local_lines=sum(len(v['lines']) for v in rows),eligible_lines=sum(v['eligible'] for row in rows for v in row['lines']),
        selected_failed_windows=[i for i,v in enumerate(rows) if not v['success']],
        augmented_adopted_windows=[i for i,v in enumerate(decisions) if v['augmented_adopted']],
        augmentation_unknown_windows=[i for i,v in enumerate(decisions) if v['reason']=='augmentation_unknown'],
        variants={key:{k:v[k] for k in ['longest_track','tracks_atleast5','components','mixed_identity_tracks','unexplained_absent_query_hits']} for key,v in scores.items()}))
    save(a.out/'report.json',r)
    return truth['rows']


def prerequisite(rows,links,truth):
    failures=[]
    for i,(row,actual) in enumerate(zip(rows,truth)):
        reasons=[]
        if not row['success']:reasons.append('optimizer_failure')
        if len(row['lines'])!=10:reasons.append('mode_count')
        if not all(v['eligible'] for v in row['lines']):reasons.append('line_eligibility')
        if len(row['lines'])==10:
            for name,key,limit in [('frequency','frequency_hz',.06),('rate','chirp_hz_per_second',.15),('curvature','curvature_hz_per_second2',1.2)]:
                if max(abs(v[key]-e[key]) for v,e in zip(row['lines'],actual['lines']))>=limit:reasons.append(name)
        with np.load(a.out/'cubic_control'/f'selected_{i:02d}.npz') as z:
            relative=float(np.linalg.norm(z['residual'])/np.linalg.norm(z['audio'])) if 'residual' in z else None
        if relative is None or relative>=1e-5:reasons.append('waveform_relative_error')
        if reasons:failures.append(dict(window=i,reasons=reasons,relative_residual=relative))
    tracks=links['selected_boundary']['tracks']
    complete=len(tracks)==10 and all(len(v['windows'])==12 for v in tracks)
    save(a.out/'prerequisite.json',dict(failures=failures,ten_complete_tracks=complete,passed=not failures and complete))
    return not failures and complete


try:
    names=['tools/observe_candidate_prediction_v1.py','research/candidate_prediction_v1_plan.json',
        'research/accel_chirp_v1_plan.json','research/low_chirp_v1_plan.json','tools/research_archive_v1.py',
        'tools/accel_low_fit_v1/observe.py','tools/low_chirp_v1/link.py']
    names += [v.relative_to(repo).as_posix() for directory in ['native_phase_patch_v1','candidate_presence_v1','candidate_prediction_v1']
              for v in (repo/'tools'/directory).glob('*.py')]
    for name in names:
        dest=a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest)
        r['sources'][name]=sha(repo/name)
    r['plan']=load(repo/'research/candidate_prediction_v1_plan.json')
    r['parent_manifest_sha256']=sha(baseline/'manifest.json')
    fp=load(repo/'research/accel_chirp_v1_plan.json')
    lp=load(repo/'research/low_chirp_v1_plan.json')
    n=12000
    t=np.arange(n)/48000-.125
    w=np.sqrt((.5-.5*np.cos(2*np.pi*np.arange(n)/n))/n)*(np.arange(n)<9000)
    nominal=np.array([76.,148.,300.])
    x=np.cos(2*np.pi*(t[:,None]*[76.3,147.7,300.2]+t[:,None]**2*[13.,-5.,11.]/2+t[:,None]**3*[20.,-10.,30.]/6)+[.2,.4,-.8])@[.2,.07,.1]
    x+=.007*np.random.default_rng(459331).normal(size=n)
    point=np.array([.31,-.43,.27,11.,-7.,15.,14.,-5.,12.])
    fun,jac,state=projection(x,nominal,w,t,.25)
    analytic=jac(point)
    numeric=[]
    for j in range(9):
        step=np.zeros(9)
        step[j]=1e-5
        numeric.append((fun(point+step)-fun(point-step))/2e-5)
    numeric=np.column_stack(numeric)
    current=state(point)
    coef=lstsq(current['weighted'],w*x,lapack_driver='gelsd')[0]
    svd=current['weighted']@coef-w*x
    control=dict(maximum_Jacobian_error=float(abs(analytic-numeric).max()),
        maximum_SVD_residual_error=float(abs(svd-fun(point)).max()),nonzero_residual_norm=float(np.linalg.norm(svd)))
    save(a.out/'projection_control.json',control)
    np.savez_compressed(a.out/'projection_control.npz',audio=x,nominal=nominal,time=t,weight=w,
        point=point,analytic=analytic,numeric=numeric,residual=fun(point),SVD_residual=svd)
    assert control['maximum_Jacobian_error']<1e-8 and control['maximum_SVD_residual_error']<1e-12
    old=load(parent(parent_root/'report.json'))
    assert old['result']=='all108_known_candidate_presence_windows_complete'
    cases=[v['case'] for v in old['summaries']]
    rows,links=run('cubic_control')
    truth=finish('cubic_control',rows,links)
    assert prerequisite(rows,links,truth),'Original exact-cubic prerequisite failed'
    r['prerequisite_passed']=True
    save(a.out/'report.json',r)
    for case in cases[1:]:
        rows,links=run(case)
        finish(case,rows,links)
    r.update(result='all108_known_full_candidate_prediction_windows_complete',
        qualification_pending_independent_audit=True,no_real_source_or_runtime_promotion=True)
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    raise
finally:save(a.out/'report.json',r)
