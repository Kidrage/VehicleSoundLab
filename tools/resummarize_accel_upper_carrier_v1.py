"""Correct defined stereo coherence without modifying any observed or predicted spectrum."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from research_archive_v1 import load,save,sha
from accel_upper_carrier_v1.spectral import summaries,stereo
a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',input_sha256=sha(a.input/'report.json'),sources={},observations=[])
try:
    for name in ['tools/resummarize_accel_upper_carrier_v1.py','tools/accel_upper_carrier_v1/spectral.py','research/accel_upper_carrier_v1_summary_fix.json']:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    known=np.zeros((17,4,4),complex);known[0,0,0]=known[0,1,1]=-1;known[2,0,0]=known[2,1,1]=1;known[2,0,1]=known[2,1,0]=.5
    known[3,0,0]=1;known[3,1,1]=-1
    result=summaries(known,32);assert result[0]['defined_stereo_bins']==1 and abs(result[0]['power_weighted_MSC']-.25)<1e-12
    assert result[1]['defined_stereo_bins']==0;np.savez_compressed(a.out/'known.npz',spectra=known)
    r['known']=dict(individual_positive_powers_required=True,negative_or_zero_not_rescued=True,power_values_unchanged=True)
    run=load(a.input/'report.json')
    for row in run['observations']:
        path=a.input/row['file'];assert sha(path)==row['sha256'];table={};invalid={}
        with np.load(path) as f:
            for name in row['summaries']:
                C=f[name];table[name]=summaries(C,12000);S=stereo(C);P=S[:,[0,1],[0,1]].real
                invalid[name]=dict(both_negative_bins=int(np.sum(np.all(P<0,axis=1))),
                    minimum_relative_power=float(P.min()/P.max()) if P.max()>0 else None)
                for old,new in zip(row['summaries'][name],table[name]):
                    for key in ['band_hz','coordinate_power','stereo_power','integrated_normalized_LR','total_stereo_bins']:assert old[key]==new[key]
        r['observations'].append(dict(segment=row['segment'],branch=row['branch'],source_file=row['file'],summaries=table,original_roundoff_bins=invalid))
    assert len(r['observations'])==12;r.update(result='all12_coherence_summaries_corrected_spectra_unchanged',original_sources_preserved=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result']),flush=True)
