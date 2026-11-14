"""Full approved F3 multiband/LR temporal dependence, including all frozen phase controls."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from scipy import signal
from research_archive_v1 import load,save,sha
from accel_upper_joint_v1.moments import connected,energy_partition,known

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},parent_files={},observations=[],coordinate_order=['4–8k L','4–8k R','8–14k L','8–14k R'])


def serial(v):
    if isinstance(v,np.ndarray):return v.tolist()
    if isinstance(v,dict):return {k:serial(x) for k,x in v.items()}
    if isinstance(v,list):return [serial(x) for x in v]
    return v


try:
    for name in ['tools/observe_accel_upper_joint_v1.py','tools/accel_upper_joint_v1/moments.py','tools/research_archive_v1.py','research/accel_upper_joint_v1_plan.json']:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    r['known'],arrays=known();np.savez_compressed(a.out/'known.npz',**arrays);save(a.out/'report.json',r);print(dict(known=r['known']),flush=True)
    parent=a.workspace/'baselines/accel_upper_inventory_v1';r['parent_manifest_sha256']=sha(parent/'manifest.json')
    table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
    def read(name):
        path=parent/name;assert sha(path)==table[name];r['parent_files'][name]=table[name];return path
    before=load(read('evidence/temporal1/report.json'))
    for segment in before['observations']:
        case=segment['segment'];folder=a.out/case;folder.mkdir()
        for branch in ['original','phase_149921','phase_277139','phase_381611']:
            parentname=f'evidence/temporal1/{case}/{branch}.npz'
            with np.load(read(parentname)) as f:
                audio=f['audio'];sos=f['sos'];old=f['filtered']
            filtered=np.column_stack([signal.sosfilt(s,audio[:,ch])[4800:-4800] for s in sos for ch in range(2)])
            assert np.array_equal(filtered[:,[0,2]],old)
            count=len(filtered)//480;power=np.mean(filtered[:count*480].reshape(count,480,4)**2,axis=1)
            tile=(4800+np.arange(count)*480+240)//12000;partition=energy_partition(power,tile);whole=connected(filtered);tiles=[]
            native_index=np.arange(4800,len(audio)-4800)//12000
            for j in np.unique(native_index):
                values=filtered[native_index==j];stats=connected(values);tiles.append(dict(tile=int(j),frames=len(values),statistics=stats))
            result=dict(segment=case,branch=branch,frames=len(audio),filtered_frames=len(filtered),tiles=len(tiles),
                whole=whole,tile_moments=tiles,energy={k:v for k,v in partition.items() if k!='residual'})
            file=folder/(branch+'.npz');np.savez_compressed(file,audio=audio,filtered=filtered,power=power,tile=tile,sos=sos,
                energy_residual=partition['residual'])
            row=serial(result);row.update(file=file.relative_to(a.out).as_posix(),sha256=sha(file),parent_name=parentname)
            r['observations'].append(row);save(a.out/'report.json',r)
        print(dict(segment=case,observations=len(r['observations'])),flush=True)
    assert len(r['observations'])==12 and sum(v['tiles'] for v in r['observations'])==192
    r.update(result='all12_joint_upper_observations_complete',same_recording_not_independent=True,source_physical_identity=False,
        new_audio=False,new_profile=False,runtime_changed=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],observations=len(r['observations'])),flush=True)
