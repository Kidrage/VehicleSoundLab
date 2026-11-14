"""All approved F3 source and phase controls, low-to-upper-power cross spectra."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from research_archive_v1 import load,save,sha
from accel_upper_link_v1.spectral import features,observe,summarize,known

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},parent_files={},observations=[],native_windows=0)
try:
    for name in ['tools/observe_accel_upper_link_v1.py','tools/accel_upper_link_v1/spectral.py','tools/research_archive_v1.py','research/accel_upper_link_v1_plan.json']:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    r['known'],arrays=known();np.savez_compressed(a.out/'known.npz',**arrays);save(a.out/'report.json',r);print(dict(known=r['known']),flush=True)
    parent=a.workspace/'baselines/accel_upper_joint_v1';r['parent_manifest_sha256']=sha(parent/'manifest.json');table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
    def read(name):
        path=parent/name;assert sha(path)==table[name];r['parent_files'][name]=table[name];return path
    before=load(read('evidence/observe1/report.json'))
    assert load(read('evidence/audit1/report.json'))['result']=='passed'
    for original in before['observations']:
        with np.load(read('evidence/observe1/'+original['file'])) as f:audio=f['audio'];sos=f['sos']
        reference,power=features(audio,sos);s=observe(reference,power);case=original['segment'];branch=original['branch'];file=a.out/f'{case}_{branch}.npz'
        np.savez_compressed(file,reference=reference,power=power,**s)
        r['native_windows']+=len(s['starts']);r['observations'].append(dict(segment=case,branch=branch,parent_file='evidence/observe1/'+original['file'],file=file.name,
            sha256=sha(file),frames=len(reference),windows=len(s['starts']),summary=summarize(s),maximum_MSC=float(s['MSC'].max())))
        save(a.out/'report.json',r);print(dict(segment=case,branch=branch,windows=len(s['starts'])),flush=True)
    assert len(r['observations'])==12 and r['native_windows']==900
    r.update(result='all12_low_to_upper_power_associations_observed',new_audio=False,new_profile=False,runtime_changed=False,
        common_phase_or_RPM_used=False,source_or_excitation_identity=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],windows=r['native_windows']),flush=True)
