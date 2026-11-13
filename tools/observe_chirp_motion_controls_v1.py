"""Run all predeclared native-path mechanism controls; no recording input."""
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
from chirp_motion_controls_v1.signals import make
from chirp_motion_controls_v1.diagnostics import nearest,exact_connection_diagnostics,summary
from accel_ridges_v1.observe import inventory
from accel_low_fit_v1.observe import initial_graphs,temporal
from native_profiled_chirp_v1.fit import fit

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},summaries=[],real_source_read=False)
try:
    source_names=['tools/observe_chirp_motion_controls_v1.py','tools/chirp_motion_controls_v1/signals.py',
        'tools/chirp_motion_controls_v1/diagnostics.py','tools/native_profiled_chirp_v1/fit.py',
        'tools/accel_low_fit_v1/observe.py','tools/accel_ridges_v1/observe.py','tools/low_chirp_v1/link.py',
        'research/chirp_motion_controls_v1_plan.json','research/accel_chirp_v1_plan.json',
        'research/accel_ridges_v1_plan.json','research/low_chirp_v1_plan.json','tools/research_archive_v1.py']
    for name in source_names:
        dest=a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest)
        r['sources'][name]=sha(repo/name)
    plan=load(repo/'research/chirp_motion_controls_v1_plan.json')
    fp=load(repo/'research/accel_chirp_v1_plan.json')
    rp=load(repo/'research/accel_ridges_v1_plan.json')
    lp=load(repo/'research/low_chirp_v1_plan.json')
    n=plan['frames']
    for case in plan['cases']:
        folder=a.out/case
        folder.mkdir()
        audio,truth=make(case,plan)
        np.savez_compressed(folder/'signal.npz',audio=audio)
        invs,guides=[],[]
        for i in range(plan['windows']):
            tile=audio[i*n:(i+1)*n]
            low=inventory(tile,dict(rp,inventory_hz=[30,200]))
            high=inventory(tile,rp)
            inv=dict(bin=low['bin']+high['bin'],hz=low['hz']+high['hz'])
            invs.append(inv)
            power=low['power_LR']+high['power_LR']
            peak=int(np.argmax(np.sum(power,axis=1)))
            guides.append(dict(native_inventory_index=peak,observed_hz=inv['hz'][peak]))
        ratios=[v['observed_hz']/guides[0]['observed_hz'] for v in guides]
        init=initial_graphs(invs,ratios,rp)
        save(folder/'initialization.json',dict(inventories=invs,guides=guides,ratios=ratios,initial=init))
        rows=[]
        for i in range(plan['windows']):
            tile=audio[i*n:(i+1)*n]
            row,z=fit(tile,np.array(invs[i]['bin'])*4,init[i]['initial_chirp'],fp)
            for k,line in enumerate(row['lines']):
                line.update(native_inventory_index=k,native_bin=invs[i]['bin'][k],native_peak_hz=invs[i]['hz'][k])
            rows.append(row)
            np.savez_compressed(folder/f'tile_{i:02d}.npz',audio=tile,**z)
            save(folder/'fits.json',rows)
            print(dict(case=case,window=i,success=row['success'],lines=len(row['lines']),eligible=sum(v['eligible'] for v in row['lines'])),flush=True)
        linked=temporal(rows,lp)
        # Truth stays outside all observation/initialization/fitting operations.
        pairs=nearest(rows,truth)
        true_linked=temporal(truth,lp) if truth else None
        inequalities=exact_connection_diagnostics(truth,lp)
        save(folder/'temporal.json',linked)
        save(folder/'truth.json',dict(rows=truth,temporal=true_linked,pairs=pairs,inequalities=inequalities))
        item=summary(case,rows,linked,true_linked,pairs,inequalities)
        r['summaries'].append(item)
        save(a.out/'report.json',r)
        print(item,flush=True)
        if case=='linear_control':
            assert all(v['success'] and len(v['lines'])==10 and all(x['eligible'] for x in v['lines']) for v in rows)
            assert len(linked['tracks'])==10 and all(len(v['windows'])==12 for v in linked['tracks'])
            assert item['maximum_unique_frequency_error_hz']<.06 and item['maximum_unique_chirp_error_hzs']<.15
            for i in range(plan['windows']):
                z=np.load(folder/f'tile_{i:02d}.npz')
                assert np.linalg.norm(z['residual'])/np.linalg.norm(z['audio'])<1e-5
    r.update(result='all60_native_AM_FM_mono_noise_mechanism_controls_complete',plan=plan,
        no_truth_initialization=True,no_new_audio_profile_or_runtime=True)
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    raise
finally:
    save(a.out/'report.json',r)
