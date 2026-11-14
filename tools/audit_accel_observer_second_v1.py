"""Independent full-native second-chaos audit; follow-up controls have truthful timing."""
import argparse,datetime,os,shutil,sys,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from research_archive_v1 import load,save,sha
from accel_observer_second_v1.independent import local,combined,known_followup

a.out.mkdir(parents=True,exist_ok=False)
for name in ['tools/audit_accel_observer_second_v1.py','tools/accel_observer_second_v1/independent.py','research/accel_observer_second_v1_audit_followup.json']:
    dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest)
r=dict(result='running',errors={},cases=0,coordinates=0)


def check(name,x,y,gate=1e-9,relative=True):
    x=np.asarray(x);y=np.asarray(y);error=float(abs(x-y).max());scale=float(max(abs(x).max(),abs(y).max()))
    if relative and scale:error/=scale
    r['errors'][name]=max(error,r['errors'].get(name,0.));assert error<=gate,(name,error,gate)


try:
    r['followup_known']=known_followup();r['followup_known_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    save(a.out/'report.json',r);print(dict(known=r['followup_known']),flush=True)
    run=load(a.input/'report.json');assert run['result'] in ['running','all12_full_native_second_chaos_and_cubic_remainders_complete']
    for name,digest in run['sources'].items():assert sha(a.input/'exact_sources'/name)==digest
    assert sha(a.input/'known.npz')==run['known_sha256']
    with np.load(a.input/'known.npz') as known:
        for index,item in enumerate(run['known']['fixtures']):
            tile=np.array(item['tile']);ls={m:local(item['gamma'],item['tau'],known[f'R{index}'],item['size'],m,100) for m in np.unique(np.unique(tile,return_counts=True)[1])}
            values,_=combined(item['gamma'],item['tau'],tile,ls,item['size'],item['blocks'],1,100)
            for key,value in values.items():check('known_'+key,value,item[key],1e-11,False)
            assert values['variance_lower_run']<=item['exact_path_variance']+1e-11<=values['variance_upper_run']+2e-11
    r['all_original_known_fixtures_independently_replayed']=True
    parent=a.workspace/'baselines/accel_observer_projection_v1';assert sha(parent/'manifest.json')==run['parent_manifest_sha256']
    table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
    for name,digest in run['parent_files'].items():assert sha(parent/name)==digest==table[name]
    audited=[]
    while r['cases']<12:
        current=load(a.input/'report.json');assert current['result']!='failed',current.get('error')
        if len(current['observations'])<=r['cases']:
            time.sleep(5);continue
        row=current['observations'][r['cases']]
        assert sha(a.input/row['file'])==row['sha256']
        for entry in row['local_files']:assert sha(a.input/entry['file'])==entry['sha256']
        with np.load(a.input/row['file']) as f,np.load(parent/row['old_parent_file']) as old:
            for key in ['actual','conditional','source_target','gamma','tau','tile','carrier_R','path_difference','carrier_difference','total_difference']:
                check('old_'+key,f[key],old[key],0,False)
            for new,key in [('prior_path_upper','combined_path_upper'),('prior_total_upper','combined_total_upper'),('prior_carrier_upper','prior_carrier_upper')]:
                check(new,f[new],old[key],0,False)
            for i in range(4):
                start=time.perf_counter();ls={}
                for entry in row['local_files']:
                    if entry['coordinate']!=i or entry.get('groups'):continue
                    m=entry['windows'];ls[m]=loc=local(float(f['gamma'][i]),float(f['tau']),f['carrier_R'][:,i],480,m,48000)
                    with np.load(a.input/entry['file']) as saved:
                        for key,value in loc.items():check('local_'+key,value,saved[key])
                values,groups=combined(float(f['gamma'][i]),float(f['tau']),f['tile'],ls)
                for key,value in values.items():check(key,value,f[key][i])
                group_entry=next(entry for entry in row['local_files'] if entry['coordinate']==i and entry.get('groups'))
                with np.load(a.input/group_entry['file']) as saved:
                    for key,value in groups.items():check('group_'+key,value,saved[key])
                check('prior_first',values['first_variance_pooled'],old['first_variance_pooled'][i])
                check('prior_expected',values['expected'],old['expected'][i])
                r['coordinates']+=1;print(dict(coordinate=r['coordinates'],segment=row['segment'],branch=row['branch'],seconds=time.perf_counter()-start),flush=True)
            cp=np.minimum(f['variance_upper_pooled'],f['prior_path_upper'])
            check('combined_path',cp,f['combined_path_upper'],0,False)
            check('combined_total',cp+f['prior_carrier_upper'],f['combined_total_upper'],0,False)
            assert np.all(f['variance_lower_pooled']<=cp+1e-12)
            for name in ['path','total']:
                prob=np.array([1. if d==0 else min(1.,v/d**2) for v,d in zip(f['combined_'+name+'_upper'],f[name+'_difference'])])
                check(name+'_tail',prob,f[name+'_tail_upper'],1e-12,False)
            for report_key,key in [('first','first_variance_pooled'),('second','second_variance_pooled'),('lower','variance_lower_pooled'),('upper','combined_path_upper'),('total_upper','combined_total_upper')]:
                check('reported_'+report_key,row[report_key],f[key],1e-12,False)
        audited.append(row);r['cases']+=1;save(a.out/'report.json',r)
    assert r['cases']==12 and r['coordinates']==48
    run=load(a.input/'report.json');assert run['result']=='all12_full_native_second_chaos_and_cubic_remainders_complete'
    assert run['observations']==audited
    for name,digest in run['parent_files'].items():assert sha(parent/name)==digest==table[name]
    r['input_sha256']=sha(a.input/'report.json');r['all_final_rows_and_parent_hashes_rechecked']=True
    r.update(result='passed',all_local_native_vectors_and_contractions=True,all_full_second_chaos_terms=True,
        all_old_values_and_bounds=True,full_variance_or_CI_qualified=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],coordinates=r['coordinates'],errors=r['errors']),flush=True)
