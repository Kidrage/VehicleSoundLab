"""Qualify one cubic-patch/boundary rule on declared synthetic cases only."""
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
from native_phase_patch_v1.basis import projection
from native_phase_patch_v1.fit import fit
from native_phase_patch_v1.inputs import observe
from native_phase_patch_v1.fixtures import mixture,annotate_previous_truth
from native_phase_patch_v1.link import link
from native_phase_patch_v1.score import score
from accel_low_fit_v1.observe import temporal

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},summaries=[],parent_files={},real_source_read=False)


def run(case,audio,observed,fp,lp,old_rows=None,old_linked=None):
    """No truth parameter is available to the observation/fitting operation."""
    folder=a.out/case
    folder.mkdir()
    np.savez_compressed(folder/'signal.npz',audio=audio)
    save(folder/'initialization.json',observed)
    rows=[]
    for i,inv in enumerate(observed['inventories']):
        tile=audio[i*12000:(i+1)*12000]
        row,z=fit(tile,np.array(inv['bin'])*4,observed['initial'][i]['initial_chirp'],fp)
        for k,line in enumerate(row['lines']):
            line.update(native_inventory_index=k,native_bin=inv['bin'][k],native_peak_hz=inv['hz'][k])
        rows.append(row)
        np.savez_compressed(folder/f'tile_{i:02d}.npz',audio=tile,**z)
        save(folder/'fits.json',rows)
        print(dict(case=case,window=i,success=row['success'],lines=len(row['lines']),
            eligible=sum(v['eligible'] for v in row['lines']),evaluations=row.get('evaluations')),flush=True)
    links=dict(new_old=temporal(rows,lp),new_new=link(rows,lp))
    if old_rows is not None:
        links.update(old_old=old_linked,old_new=link(old_rows,lp))
    save(folder/'links.json',links)
    return rows,links


def finish(case,rows,links,truth,lp):
    folder=a.out/case
    scores={key:score(value,truth) for key,value in links.items()}
    save(folder/'truth.json',dict(rows=truth,boundary=link(truth,lp) if truth else None))
    save(folder/'scores.json',scores)
    item=dict(case=case,windows=len(rows),successful=sum(v['success'] for v in rows),
        local_lines=sum(len(v['lines']) for v in rows),eligible_lines=sum(v['eligible'] for row in rows for v in row['lines']),
        failed_windows=[i for i,v in enumerate(rows) if not v['success']],
        variants={key:dict(longest_track=v['longest_track'],tracks_atleast5=v['tracks_atleast5'],
            components=v['components'],mixed_identity_tracks=v['mixed_identity_tracks'],
            unexplained_absent_query_hits=v['unexplained_absent_query_hits']) for key,v in scores.items()})
    r['summaries'].append(item)
    save(a.out/'report.json',r)
    print(dict(case=case,summary={key:[v['longest_track'],v['tracks_atleast5'],len(v['mixed_identity_tracks'])] for key,v in scores.items()}),flush=True)
    return scores


try:
    names=['tools/observe_phase_patch_v1.py','research/phase_patch_v1_plan.json',
        'research/accel_chirp_v1_plan.json','research/accel_ridges_v1_plan.json','research/low_chirp_v1_plan.json',
        'tools/research_archive_v1.py','tools/accel_low_fit_v1/observe.py','tools/low_chirp_v1/link.py','tools/accel_ridges_v1/observe.py']
    names += [v.relative_to(repo).as_posix() for v in (repo/'tools/native_phase_patch_v1').glob('*.py')]
    for name in names:
        dest=a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest)
        r['sources'][name]=sha(repo/name)
    plan=load(repo/'research/phase_patch_v1_plan.json')
    fp=load(repo/'research/accel_chirp_v1_plan.json')
    rp=load(repo/'research/accel_ridges_v1_plan.json')
    lp=load(repo/'research/low_chirp_v1_plan.json')
    baseline=a.workspace/'baselines/chirp_motion_controls_v1'
    manifest=load(baseline/'manifest.json')
    lookup={v['path']:v['sha256'] for v in manifest['files']}
    parent=baseline/'evidence/observe1'
    def read_parent(path):
        name=path.relative_to(baseline).as_posix()
        h=sha(path)
        assert lookup[name]==h
        r['parent_files'][name]=h
        return path
    previous=load(read_parent(parent/'report.json'))
    assert previous['result']=='all60_native_AM_FM_mono_noise_mechanism_controls_complete'
    p0=previous['plan']
    r['parent_manifest_sha256']=sha(baseline/'manifest.json')
    n=12000
    t=np.arange(n)/48000-.125
    w=np.sqrt((.5-.5*np.cos(2*np.pi*np.arange(n)/n))/n)
    nominal=np.array([76.,148.,300.])
    x=np.cos(2*np.pi*(t[:,None]*[76.3,147.7,300.2]+.5*t[:,None]**2*[13.,-5.,11.]+t[:,None]**3*[20.,-10.,30.]/6)+[.2,.4,-.8])@[.2,.07,.1]
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
    s=state(point)
    coeff=lstsq(s['weighted'],w*x,lapack_driver='gelsd')[0]
    svd=s['weighted']@coeff-w*x
    control=dict(maximum_Jacobian_error=float(abs(analytic-numeric).max()),
        maximum_SVD_residual_error=float(abs(svd-fun(point)).max()),nonzero_residual_norm=float(np.linalg.norm(svd)))
    save(a.out/'projection_control.json',control)
    np.savez_compressed(a.out/'projection_control.npz',audio=x,nominal=nominal,time=t,weight=w,
        point=point,analytic=analytic,numeric=numeric,residual=fun(point),SVD_residual=svd)
    assert control['maximum_Jacobian_error']<1e-8 and control['maximum_SVD_residual_error']<1e-12
    print(dict(stage='nonzero_residual_Jacobian_pass',**control),flush=True)
    audio,truth=mixture('cubic_control',p0)
    observed=observe(audio,n,rp)
    rows,links=run('cubic_control',audio,observed,fp,lp)
    finish('cubic_control',rows,links,truth,lp)
    for i,(row,actual) in enumerate(zip(rows,truth)):
        assert row['success'] and len(row['lines'])==10 and all(v['eligible'] for v in row['lines'])
        assert max(abs(v['frequency_hz']-e['frequency_hz']) for v,e in zip(row['lines'],actual['lines']))<.06
        assert max(abs(v['chirp_hz_per_second']-e['chirp_hz_per_second']) for v,e in zip(row['lines'],actual['lines']))<.15
        assert max(abs(v['curvature_hz_per_second2']-e['curvature_hz_per_second2']) for v,e in zip(row['lines'],actual['lines']))<1.2
        z=np.load(a.out/'cubic_control'/f'tile_{i:02d}.npz')
        assert np.linalg.norm(z['residual'])/np.linalg.norm(z['audio'])<1e-5
    assert len(links['new_new']['tracks'])==10 and all(len(v['windows'])==12 for v in links['new_new']['tracks'])
    r['prerequisite_passed']=True
    save(a.out/'report.json',r)
    for case in p0['cases']:
        source=parent/case
        audio=np.load(read_parent(source/'signal.npz'))['audio']
        observed=load(read_parent(source/'initialization.json'))
        old=load(read_parent(source/'fits.json'))
        old_linked=load(read_parent(source/'temporal.json'))
        rows,links=run(case,audio,observed,fp,lp,old,old_linked)
        truth=annotate_previous_truth(case,load(read_parent(source/'truth.json'))['rows'],p0)
        finish(case,rows,links,truth,lp)
    for case in ['occluded_component','missing_component_neighbor','crossing_pair']:
        audio,truth=mixture(case,p0)
        observed=observe(audio,n,rp)
        rows,links=run(case,audio,observed,fp,lp)
        finish(case,rows,links,truth,lp)
    r.update(result='all108_known_phase_patch_fits_and_boundary_comparisons_complete',plan=plan,
        known_source_qualification_pending_independent_audit=True,no_real_source_or_runtime_promotion=True)
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    raise
finally:
    save(a.out/'report.json',r)
