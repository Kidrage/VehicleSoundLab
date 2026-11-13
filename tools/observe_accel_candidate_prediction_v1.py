"""All48 original F3 cubic native and complete candidate prediction/adoption."""
import argparse
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor,as_completed
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
from accel_low_fit_v1.observe import temporal,predictions
from candidate_presence_v1.propose import propose
from candidate_presence_v1.presence import accept
from candidate_prediction_v1.fit import fit as fit_verification
from candidate_prediction_v1.decision import decide

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},parent_files={},observations=[],real_source_read=False,
    native_windows_completed=0,selected_windows_completed=0,workers=4)
manifests={}


def parent(path,baseline):
    if str(baseline) not in manifests:
        manifests[str(baseline)]={v['path']:v['sha256'] for v in load(baseline/'manifest.json')['files']}
        r.setdefault('parent_manifests',{})[str(baseline/'manifest.json')]=sha(baseline/'manifest.json')
    name=path.relative_to(baseline).as_posix()
    h=sha(path)
    assert manifests[str(baseline)][name]==h
    r['parent_files'][str(path)]=h
    return path


def native_job(tile,inv,initial,metadata):
    started=time.perf_counter()
    row,z=fit(tile,np.array(inv['bin'])*4,initial['initial_chirp'],fp)
    row.update(**metadata,offline_seconds=time.perf_counter()-started)
    return row,z


def verification_job(tile,nominal,chirp):
    started=time.perf_counter()
    row,z=fit_verification(tile,nominal,chirp,fp)
    row['offline_seconds']=time.perf_counter()-started
    return row,z


try:
    names=['tools/observe_accel_candidate_prediction_v1.py','research/accel_candidate_prediction_v1_plan.json',
        'research/accel_chirp_v1_plan.json','research/low_chirp_v1_plan.json','tools/research_archive_v1.py',
        'tools/accel_low_fit_v1/observe.py','tools/low_chirp_v1/link.py']
    names += [v.relative_to(repo).as_posix() for directory in ['native_phase_patch_v1','candidate_presence_v1','candidate_prediction_v1']
              for v in (repo/'tools'/directory).glob('*.py')]
    known_baseline=a.workspace/'baselines/candidate_prediction_v1'
    known=load(parent(known_baseline/'evidence/audit2/report.json',known_baseline))
    assert known['qualified_known_controls'] and known['windows']==108 and known['verification_fits']==46
    for name in ['tools/native_phase_patch_v1/fit.py','tools/native_phase_patch_v1/basis.py','tools/native_phase_patch_v1/link.py',
        'tools/candidate_presence_v1/propose.py','tools/candidate_presence_v1/presence.py',
        'tools/candidate_prediction_v1/fit.py','tools/candidate_prediction_v1/decision.py']:
        assert sha(repo/name)==sha(parent(known_baseline/'source'/name,known_baseline))
    for name in names:
        dest=a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest)
        r['sources'][name]=sha(repo/name)
    r['plan']=load(repo/'research/accel_candidate_prediction_v1_plan.json')
    fp=load(repo/'research/accel_chirp_v1_plan.json')
    lp=load(repo/'research/low_chirp_v1_plan.json')
    base=a.workspace/'baselines/accel_low_fit_v1'
    profiled=a.workspace/'baselines/accel_low_profiled_v1'
    with ThreadPoolExecutor(max_workers=4) as pool:
        for case in ['F3_fifth1','F3_fifth2','F3_sixth']:
            source=base/'evidence/observe2'/case
            folder=a.out/case
            folder.mkdir()
            observed=load(parent(source/'initialization.json',base))
            originals=load(parent(source/'fits.json',base))
            old=load(parent(profiled/'evidence/observe1'/case/'fits.json',profiled))
            old_link=load(parent(profiled/'evidence/observe1'/case/'temporal.json',profiled))
            save(folder/'initialization.json',observed)
            save(folder/'original_linear_fits.json',originals)
            save(folder/'profiled_linear_fits.json',old)
            tiles=[]
            native=[None]*len(originals)
            pending={}
            for i,inv in enumerate(observed['inventories']):
                tile=np.load(parent(source/f'tile_{i:02d}.npz',base))['audio']
                tiles.append(tile)
                metadata=dict(tile=i,ratio=originals[i]['ratio'],guide_supported=originals[i]['guide_supported'])
                pending[pool.submit(native_job,tile,inv,observed['initial'][i],metadata)]=i
            r['real_source_read']=True
            for future in as_completed(pending):
                i=pending[future]
                native[i],z=future.result()
                np.savez_compressed(folder/f'native_{i:02d}.npz',audio=tiles[i],**z)
                save(folder/'native_fits.json',native)
                r['native_windows_completed']+=1
                save(a.out/'report.json',r)
                print(dict(case=case,stage='native',window=i,success=native[i]['success'],modes=len(native[i]['lines']),
                    eligible=sum(v['eligible'] for v in native[i]['lines']),seconds=round(native[i]['offline_seconds'],3)),flush=True)
            audio=np.concatenate(tiles)
            np.savez_compressed(folder/'signal.npz',audio=audio)
            rows,raws,postfits,proposals,presences,verifications,decisions=[],[],[],[],[],[],[]
            for i,(tile,inv,native_row) in enumerate(zip(tiles,observed['inventories'],native)):
                with np.load(folder/f'native_{i:02d}.npz') as loaded:
                    nz={k:loaded[k] for k in loaded.files if k!='audio'}
                previous=rows[-1] if rows else None
                proposal=propose(inv,observed['initial'][i],previous)
                nominal=np.array(proposal['inventory']['bin'])*4
                chirp=np.array(proposal['initial_chirp'])
                if proposal['added_bins']:
                    started=time.perf_counter()
                    raw,z=fit(tile,nominal,chirp,fp)
                    raw.update(tile=i,ratio=native_row['ratio'],guide_supported=native_row['guide_supported'],
                        offline_seconds=time.perf_counter()-started)
                    present_future=pool.submit(verification_job,tile,nominal,chirp)
                    deletes={}
                    for cell in proposal['added_bins']:
                        keep=np.array([v!=cell for v in proposal['inventory']['bin']])
                        deletes[cell]=pool.submit(verification_job,tile,nominal[keep],chirp[keep])
                    training,tz=present_future.result()
                    np.savez_compressed(folder/f'verify_present_{i:02d}.npz',audio=tile,**tz)
                    deleted={}
                    for cell,future in deletes.items():
                        deleted[cell],dz=future.result()
                        np.savez_compressed(folder/f'verify_deleted_{i:02d}_{cell:04d}.npz',audio=tile,**dz)
                else:
                    raw,z=native_row,nz
                    training,deleted=None,{}
                postfit,presence=accept(raw,z,tile,proposal,previous)
                chosen,decision=decide(native_row,raw,postfit,proposal,training,deleted)
                selected_z=z if decision['augmented_adopted'] else nz
                rows.append(chosen)
                raws.append(raw)
                postfits.append(postfit)
                proposals.append(proposal)
                presences.append(presence)
                verifications.append(dict(present=training,deleted=deleted))
                decisions.append(decision)
                np.savez_compressed(folder/f'tile_{i:02d}.npz',audio=tile,**z)
                np.savez_compressed(folder/f'selected_{i:02d}.npz',audio=tile,**selected_z)
                for name,value in [('raw_fits',raws),('augmented_accepted_fits',postfits),('fits',rows),
                    ('proposals',proposals),('presence',presences),('verification_fits',verifications),('decisions',decisions)]:save(folder/(name+'.json'),value)
                r['selected_windows_completed']+=1
                save(a.out/'report.json',r)
                print(dict(case=case,stage='selection',window=i,added=proposal['added_bins'],full_success=raw['success'],
                    reason=decision['reason'],selected_eligible=sum(v['eligible'] for v in chosen['lines'])),flush=True)
            links=dict(profiled_old=old_link,profiled_boundary=link(old,lp),native_old=temporal(native,lp),
                native_boundary=link(native,lp),selected_old=temporal(rows,lp),selected_boundary=link(rows,lp))
            save(folder/'links.json',links)
            predicted={key:predictions(old if key.startswith('profiled') else native if key.startswith('native') else rows,value) for key,value in links.items()}
            save(folder/'predictions.json',predicted)
            summary=dict(segment=case,windows=len(rows),native_successful=sum(v['success'] for v in native),
                augmented_attempts=sum(bool(v['added_bins']) for v in proposals),
                selected_successful=sum(v['success'] for v in rows),
                native_lines=sum(len(v['lines']) for v in native),raw_lines=sum(len(v['lines']) for v in raws),
                selected_lines=sum(len(v['lines']) for v in rows),selected_eligible=sum(v['eligible'] for row in rows for v in row['lines']),
                adopted_windows=[i for i,v in enumerate(decisions) if v['augmented_adopted']],
                unknown_windows=[i for i,v in enumerate(decisions) if v['reason']=='augmentation_unknown'],
                variants={key:dict(longest_low_start_track=max((len(v['windows']) for v in value['tracks'] if v['frequencies_hz'][0]<200),default=0),
                    low_start_tracks_atleast5=sum(v['frequencies_hz'][0]<200 and len(v['windows'])>=5 for v in value['tracks']),
                    compared_low_tracks=sum(v['status']=='compared' for v in predicted[key])) for key,value in links.items()})
            r['observations'].append(summary)
            save(a.out/'report.json',r)
            print(summary,flush=True)
    assert r['native_windows_completed']==r['selected_windows_completed']==48
    r.update(result='all48_original_F3_cubic_candidate_prediction_observations_complete',
        new_audio_or_profile=False,runtime_changed=False,qualification_pending_independent_audit=True,
        physical_source_RPM_load_or_common_phase_identified=False)
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    raise
finally:save(a.out/'report.json',r)
