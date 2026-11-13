"""Qualify current-residual screening before observed candidate insertion."""
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
from native_phase_patch_v1.link import link
from native_phase_patch_v1.score import score
from accel_low_fit_v1.observe import temporal
from candidate_presence_v1.propose import propose
from candidate_presence_v1.presence import accept
from candidate_residual_v1.screen import select

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},parent_files={},summaries=[],real_source_read=False,
    prerequisite_passed=False,planned_windows=108,executed_windows=0)
baseline=a.workspace/'baselines/candidate_presence_v1'
parent_root=baseline/'evidence/observe1'
manifest=load(baseline/'manifest.json')
table={v['path']:v['sha256'] for v in manifest['files']}


def parent(path):
    h=sha(path)
    name=path.relative_to(baseline).as_posix()
    assert table[name]==h
    r['parent_files'][name]=h
    return path


def run(case):
    source=parent_root/case
    folder=a.out/case
    folder.mkdir()
    audio=np.load(parent(source/'signal.npz'))['audio']
    observed=load(parent(source/'initialization.json'))
    natives=load(parent(source/'native_fits.json'))
    shutil.copy2(source/'signal.npz',folder/'signal.npz')
    save(folder/'initialization.json',observed)
    save(folder/'native_fits.json',natives)
    rows,raws,proposals,candidates,screens,checks=[],[],[],[],[],[]
    for i,(inv,native) in enumerate(zip(observed['inventories'],natives)):
        tile=audio[i*12000:(i+1)*12000]
        with np.load(parent(source/f'native_{i:02d}.npz')) as loaded:
            arrays={k:loaded[k] for k in loaded.files if k!='audio'}
        previous=rows[-1] if rows else None
        candidate=propose(inv,observed['initial'][i],previous)
        proposal,screen,sz=select(native,arrays,tile,candidate,previous,fp)
        if proposal is None:
            raw,z=dict(success=False,reason='empty_or_overflow',lines=[]),{}
            # Retain the full rejected inventory, without truncation or retry.
            proposal=candidate
        elif proposal['added_bins']:
            raw,z=fit(tile,np.array(proposal['inventory']['bin'])*4,proposal['initial_chirp'],fp)
        else:raw,z=native,arrays
        accepted,check=accept(raw,z,tile,proposal,previous)
        rows.append(accepted)
        raws.append(raw)
        candidates.append(candidate)
        proposals.append(proposal)
        screens.append(screen)
        checks.append(check)
        np.savez_compressed(folder/f'tile_{i:02d}.npz',audio=tile,**z)
        np.savez_compressed(folder/f'screen_{i:02d}.npz',**sz)
        for name,value in [('raw_fits',raws),('fits',rows),('candidate_proposals',candidates),
                           ('proposals',proposals),('screens',screens),('presence',checks)]:save(folder/(name+'.json'),value)
        r['executed_windows']+=1
        save(a.out/'report.json',r)
        print(dict(case=case,window=i,proposed=candidate['added_bins'],screen_passed=proposal['added_bins'],
            success=raw['success'],modes=len(raw['lines']),eligible=sum(v['eligible'] for v in accepted['lines'])),flush=True)
    old=load(parent(source/'links.json'))
    links=dict(native_old=old['native_old'],native_boundary=old['native_boundary'],
        unscreened_old=old['augmented_old'],unscreened_boundary=old['augmented_boundary'],
        screened_old=temporal(rows,lp),screened_boundary=link(rows,lp))
    if 'previous_old' in old:links.update(previous_old=old['previous_old'],previous_boundary=old['previous_boundary'])
    save(folder/'links.json',links)
    return rows,links


def finish(case,rows,links):
    truth=load(parent(parent_root/case/'truth.json'))
    save(a.out/case/'truth.json',truth)
    scores={key:score(value,truth['rows']) for key,value in links.items()}
    save(a.out/case/'scores.json',scores)
    r['summaries'].append(dict(case=case,windows=len(rows),successful=sum(v['success'] for v in rows),
        local_lines=sum(len(v['lines']) for v in rows),eligible_lines=sum(v['eligible'] for row in rows for v in row['lines']),
        failed_windows=[i for i,v in enumerate(rows) if not v['success']],
        variants={key:{k:v[k] for k in ['longest_track','tracks_atleast5','components',
            'mixed_identity_tracks','unexplained_absent_query_hits']} for key,v in scores.items()}))
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
            for name,key,limit in [('frequency','frequency_hz',.06),('rate','chirp_hz_per_second',.15),
                                  ('curvature','curvature_hz_per_second2',1.2)]:
                if max(abs(v[key]-e[key]) for v,e in zip(row['lines'],actual['lines']))>=limit:reasons.append(name)
        with np.load(a.out/'cubic_control'/f'tile_{i:02d}.npz') as z:
            relative=float(np.linalg.norm(z['residual'])/np.linalg.norm(z['audio'])) if 'residual' in z else None
        if relative is None or relative>=1e-5:reasons.append('waveform_relative_error')
        if reasons:failures.append(dict(window=i,reasons=reasons,relative_residual=relative))
    tracks=links['screened_boundary']['tracks']
    complete=len(tracks)==10 and all(len(v['windows'])==12 for v in tracks)
    save(a.out/'prerequisite.json',dict(failures=failures,ten_complete_tracks=complete,passed=not failures and complete))
    return not failures and complete


try:
    names=['tools/observe_candidate_residual_v1.py','research/candidate_residual_v1_plan.json',
        'research/accel_chirp_v1_plan.json','research/low_chirp_v1_plan.json',
        'tools/research_archive_v1.py','tools/accel_low_fit_v1/observe.py','tools/low_chirp_v1/link.py']
    names += [v.relative_to(repo).as_posix() for directory in ['native_phase_patch_v1','candidate_presence_v1','candidate_residual_v1']
              for v in (repo/'tools'/directory).glob('*.py')]
    for name in names:
        dest=a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest)
        r['sources'][name]=sha(repo/name)
    r['plan']=load(repo/'research/candidate_residual_v1_plan.json')
    r['parent_manifest_sha256']=sha(baseline/'manifest.json')
    fp=load(repo/'research/accel_chirp_v1_plan.json')
    lp=load(repo/'research/low_chirp_v1_plan.json')
    old=load(parent(parent_root/'report.json'))
    assert old['result']=='all108_known_candidate_presence_windows_complete'
    cases=[v['case'] for v in old['summaries']]
    assert len(cases)==9 and cases[0]=='cubic_control'
    rows,links=run('cubic_control')
    truth=finish('cubic_control',rows,links)
    assert prerequisite(rows,links,truth),'Original exact-cubic prerequisite failed'
    r['prerequisite_passed']=True
    save(a.out/'report.json',r)
    for case in cases[1:]:
        rows,links=run(case)
        finish(case,rows,links)
    r.update(result='all108_known_candidate_residual_windows_complete',
        qualification_pending_independent_audit=True,no_real_source_or_runtime_promotion=True)
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    raise
finally:save(a.out/'report.json',r)
