"""Causal native candidate proposals and current-wave presence, known cases only."""
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
from research_archive_v1 import load,save,sha
from native_phase_patch_v1.fit import fit
from native_phase_patch_v1.inputs import observe
from native_phase_patch_v1.fixtures import mixture,annotate_previous_truth
from native_phase_patch_v1.link import link
from native_phase_patch_v1.score import score
from accel_low_fit_v1.observe import temporal
from candidate_presence_v1.propose import propose
from candidate_presence_v1.presence import accept

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},parent_files={},summaries=[],real_source_read=False,
    prerequisite_passed=False,planned_windows=108,executed_windows=0)


def parent(path,baseline):
    manifest=load(baseline/'manifest.json')
    table={v['path']:v['sha256'] for v in manifest['files']}
    name=path.relative_to(baseline).as_posix()
    h=sha(path)
    assert table[name]==h
    r['parent_files'][str(path)]=h
    return path


def run(case,audio,observed,frozen=None,old=None,old_link=None):
    """Estimation has no truth argument or access to known component slots."""
    folder=a.out/case
    folder.mkdir()
    np.savez_compressed(folder/'signal.npz',audio=audio)
    save(folder/'initialization.json',observed)
    rows,raws,natives,proposals,checks=[],[],[],[],[]
    for i,inv in enumerate(observed['inventories']):
        tile=audio[i*12000:(i+1)*12000]
        if frozen is not None:
            native=load(parent(frozen/'fits.json',phase_baseline))[i]
            with np.load(parent(frozen/f'tile_{i:02d}.npz',phase_baseline)) as loaded:
                arrays={k:loaded[k] for k in loaded.files if k!='audio'}
        else:
            native,arrays=fit(tile,np.array(inv['bin'])*4,observed['initial'][i]['initial_chirp'],fp)
        natives.append(native)
        np.savez_compressed(folder/f'native_{i:02d}.npz',audio=tile,**arrays)
        proposal=propose(inv,observed['initial'][i],rows[-1] if rows else None)
        proposals.append(proposal)
        if proposal['added_bins']:
            raw,z=fit(tile,np.array(proposal['inventory']['bin'])*4,proposal['initial_chirp'],fp)
        else:
            raw,z=native,arrays
        accepted,test=accept(raw,z,tile,proposal,rows[-1] if rows else None)
        raws.append(raw)
        rows.append(accepted)
        checks.append(test)
        np.savez_compressed(folder/f'tile_{i:02d}.npz',audio=tile,**z)
        for name,value in [('native_fits',natives),('raw_fits',raws),('fits',rows),
                           ('proposals',proposals),('presence',checks)]:save(folder/(name+'.json'),value)
        r['executed_windows']+=1
        save(a.out/'report.json',r)
        print(dict(case=case,window=i,native_modes=len(native['lines']),added=proposal['added_bins'],
            success=raw['success'],modes=len(raw['lines']),eligible=sum(v['eligible'] for v in accepted['lines']),
            augmented_evaluations=raw.get('evaluations') if proposal['added_bins'] else 0),flush=True)
    links=dict(native_old=temporal(natives,lp),native_boundary=link(natives,lp),
        augmented_old=temporal(rows,lp),augmented_boundary=link(rows,lp))
    if old is not None:links.update(previous_old=old_link,previous_boundary=link(old,lp))
    save(folder/'links.json',links)
    return rows,links


def finish(case,rows,links,truth):
    folder=a.out/case
    scores={key:score(value,truth) for key,value in links.items()}
    save(folder/'truth.json',dict(rows=truth,boundary=link(truth,lp) if truth else None))
    save(folder/'scores.json',scores)
    item=dict(case=case,windows=len(rows),successful=sum(v['success'] for v in rows),
        local_lines=sum(len(v['lines']) for v in rows),
        eligible_lines=sum(v['eligible'] for row in rows for v in row['lines']),
        failed_windows=[i for i,v in enumerate(rows) if not v['success']],
        variants={key:{k:v[k] for k in ['longest_track','tracks_atleast5','components',
            'mixed_identity_tracks','unexplained_absent_query_hits']} for key,v in scores.items()})
    r['summaries'].append(item)
    save(a.out/'report.json',r)
    return scores


def prerequisite(rows,links,truth):
    failures=[]
    for i,(row,actual) in enumerate(zip(rows,truth)):
        reasons=[]
        if not row['success']:reasons.append('optimizer_failure')
        if len(row['lines'])!=10:reasons.append('mode_count')
        if not all(v['eligible'] for v in row['lines']):reasons.append('line_eligibility')
        if len(row['lines'])==10:
            for name,key,limit in [('frequency','frequency_hz',.06),('rate','chirp_hz_per_second',.15),
                                  ('curvature','curvature_hz_per_second2',1.2)]:
                if max(abs(v[key]-e[key]) for v,e in zip(row['lines'],actual['lines']))>=limit:reasons.append(name)
        with np.load(a.out/'cubic_control'/f'tile_{i:02d}.npz') as z:
            relative=float(np.linalg.norm(z['residual'])/np.linalg.norm(z['audio'])) if 'residual' in z else None
        if relative is None or relative>=1e-5:reasons.append('waveform_relative_error')
        if reasons:failures.append(dict(window=i,reasons=reasons,relative_residual=relative))
    tracks=links['augmented_boundary']['tracks']
    complete=len(tracks)==10 and all(len(v['windows'])==12 for v in tracks)
    save(a.out/'prerequisite.json',dict(failures=failures,ten_complete_tracks=complete,passed=not failures and complete))
    return not failures and complete


try:
    names=['tools/observe_candidate_presence_v1.py','research/candidate_presence_v1_plan.json',
        'research/accel_chirp_v1_plan.json','research/accel_ridges_v1_plan.json','research/low_chirp_v1_plan.json',
        'tools/research_archive_v1.py','tools/accel_low_fit_v1/observe.py','tools/low_chirp_v1/link.py',
        'tools/accel_ridges_v1/observe.py']
    names += [v.relative_to(repo).as_posix() for directory in ['native_phase_patch_v1','candidate_presence_v1']
              for v in (repo/'tools'/directory).glob('*.py')]
    for name in names:
        dest=a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest)
        r['sources'][name]=sha(repo/name)
    r['plan']=load(repo/'research/candidate_presence_v1_plan.json')
    fp=load(repo/'research/accel_chirp_v1_plan.json')
    rp=load(repo/'research/accel_ridges_v1_plan.json')
    lp=load(repo/'research/low_chirp_v1_plan.json')
    phase_baseline=a.workspace/'baselines/phase_patch_v1'
    motion_baseline=a.workspace/'baselines/chirp_motion_controls_v1'
    frozen=phase_baseline/'evidence/observe1/cubic_control'
    motion=motion_baseline/'evidence/observe1'
    r['parent_manifests']={str(v/'manifest.json'):sha(v/'manifest.json') for v in [phase_baseline,motion_baseline]}
    p0=load(parent(motion/'report.json',motion_baseline))['plan']
    audio=np.load(parent(frozen/'signal.npz',phase_baseline))['audio']
    observed=load(parent(frozen/'initialization.json',phase_baseline))
    rows,links=run('cubic_control',audio,observed,frozen=frozen)
    truth=load(parent(frozen/'truth.json',phase_baseline))['rows']
    finish('cubic_control',rows,links,truth)
    assert prerequisite(rows,links,truth),'Original exact-cubic prerequisite failed'
    r['prerequisite_passed']=True
    save(a.out/'report.json',r)
    for case in p0['cases']:
        source=motion/case
        audio=np.load(parent(source/'signal.npz',motion_baseline))['audio']
        observed=load(parent(source/'initialization.json',motion_baseline))
        old=load(parent(source/'fits.json',motion_baseline))
        old_link=load(parent(source/'temporal.json',motion_baseline))
        rows,links=run(case,audio,observed,old=old,old_link=old_link)
        truth=annotate_previous_truth(case,load(parent(source/'truth.json',motion_baseline))['rows'],p0)
        finish(case,rows,links,truth)
    for case in ['occluded_component','missing_component_neighbor','crossing_pair']:
        audio,truth=mixture(case,p0)
        observed=observe(audio,12000,rp)
        rows,links=run(case,audio,observed)
        finish(case,rows,links,truth)
    r.update(result='all108_known_candidate_presence_windows_complete',
        qualification_pending_independent_audit=True,no_real_source_or_runtime_promotion=True)
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    raise
finally:
    save(a.out/'report.json',r)
