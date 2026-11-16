"""Known pair-accounting controls, then read-only six-profile source tracing."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from phase_source_support_v1.measure import shared_pairs,describe
    from c1_registered_source_v1.binding import protected
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',sources={},inputs={},known=[],cases=[])
    try:
        protected(a.workspace,repo)
        for name in ('research/phase_source_support_v1_plan.json','tools/run_phase_source_support_v1.py',
            'tools/audit_phase_source_support_v1.py','tools/phase_source_support_v1/__init__.py',
            'tools/phase_source_support_v1/measure.py','tools/research_archive_v1.py'):
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        def consume(path):r['inputs'][str(path)]=sha(path);return load(path)
        controls=np.column_stack((np.cos(np.arange(11)*.31),np.sin(np.arange(11)*.31),np.cos(np.arange(11)*.71)))
        b=np.array([[1.,1.,0.],[1.,-1.,0.],[0.,0.,2.],[2.,0.,0.]])
        for label,pc,basis in (('coupled',controls,b),('signed',controls*np.array([-1,1,-1]),b*np.array([-1,1,-1])),
            ('permuted',controls[:,[2,0,1]],b[:,[2,0,1]]),('zero',np.zeros_like(controls),b)):
            pairs,feature,arrays=shared_pairs(pc,basis)
            x=pc@basis.T;x-=x.mean(axis=0)
            c=x[1:].T@x[:-1]/(len(x)-1);dense=(c-c.T)/2
            direct=float(np.sum(dense*dense));reported=sum(v['squared_feature_skew_norm'] for v in pairs)
            assert abs(direct-reported)<2e-11 and abs(feature.sum()-1)<2e-11
            r['known'].append(dict(label=label,dense_squared_norm=direct,pair_squared_norm=reported,
                absolute_error=abs(direct-reported)))
        assert abs(r['known'][0]['dense_squared_norm']-r['known'][1]['dense_squared_norm'])<2e-11
        assert abs(r['known'][0]['dense_squared_norm']-r['known'][2]['dense_squared_norm'])<2e-11
        assert r['known'][3]['dense_squared_norm']==0
        save(a.out/'report.json',r)
        native=a.workspace/'references/analysis/phase_observation_native_v1'
        qualification=consume(native/'known_audit2/report.json')
        assert qualification['verification_passed'] and qualification['producer_sha256']==sha(native/'known2/report.json')
        consume(native/'known2/report.json')
        old=a.workspace/'references/analysis/relative_phase_v1'
        saved=consume(old/'real1/report.json');audit=consume(old/'real_audit2/report.json')
        assert saved['result']=='six_source_relative_phase_evidence_ready'
        assert audit['result']=='independent_relative_phase_audit_passed' and audit['producer_sha256']==sha(old/'real1/report.json')
        geometry=a.workspace/'baselines/coefficient_geometry_v1'
        entries={v['path']:v['sha256'] for v in consume(geometry/'manifest.json')['files']}
        provenance=consume(geometry/'evidence/real1/report.json')
        assert sha(geometry/'evidence/real1/report.json')==entries['evidence/real1/report.json']
        for row in saved['cases']:
            label=row['label'];paths={}
            for name,digest in (('profile',row['profile_sha256']),('training',row['training_sha256'])):
                path=old/'real1'/label/(name+'.npz');assert sha(path)==digest;r['inputs'][str(path)]=digest;paths[name]=path
            packet=geometry/('evidence/real1/'+label+'/source.npz')
            digest=entries[packet.relative_to(geometry).as_posix()];assert sha(packet)==digest;r['inputs'][str(packet)]=digest
            moments=geometry/('evidence/real1/'+label+'/full/moments.npz')
            digest=entries[moments.relative_to(geometry).as_posix()];assert sha(moments)==digest;r['inputs'][str(moments)]=digest
            with np.load(paths['training']) as f:training={k:f[k] for k in f.files}
            with np.load(moments) as f:assert np.array_equal(training['source_rows'],f['rows'])
            with np.load(paths['profile']) as f:profile={k:f[k] for k in f.files}
            with np.load(packet) as f:positions=f['positions']
            pairs,arrays,meta=describe(training,profile,positions,row['root_hz'])
            folder=a.out/label;folder.mkdir();np.savez_compressed(folder/'trace.npz',**arrays)
            original=next(v for v in provenance['cases'] if v['label']==label)
            r['cases'].append(dict(label=label,source_start_seconds=original['source_start'],
                source_profile_path=str(paths['profile']),source_training_path=str(paths['training']),source_packet=str(packet),
                trace_sha256=sha(folder/'trace.npz'),pairs=pairs,metadata=meta))
            save(a.out/'report.json',r);print('SOURCE_SUPPORT',label,'leading_pair',pairs[0]['pc_i']+1,pairs[0]['pc_j']+1,flush=True)
        assert len(r['cases'])==6
        r.update(result='saved_six_shared_feature_directions_traced_to_sources',no_refit_training_audio_C_change=True,
            new_C1_source_eligible_for_statistics=False,full_goal='ACTIVE')
        save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
