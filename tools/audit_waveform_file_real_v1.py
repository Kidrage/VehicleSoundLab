"""Audit one terminal real case, or qualify this new auditor on prior controls."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('workspace','study','out'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--known-check',action='store_true')
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    from waveform_file_real_v1.audit import verify
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',cases=[],inputs={})
    try:
        if a.known_check:
            source=load(a.study/'report.json');assert source['result']=='waveform_file_real_adapter_known_measured'
            directories=[a.study/c['label'] for c in source['cases'] if c['label']!='both_zero']
            # New generic audit wasn't present during the earlier known run.
            # Its numerical conclusions must agree with that frozen independent audit.
            oldpath=a.study.parent/'known_audit1/report.json';old=load(oldpath)
            assert old['all_qualified'];r['inputs'][str(oldpath)]=sha(oldpath)
        else:
            source=load(a.study.parent/'run_spec.json')
            directories=[a.study]
            assert len(source['declared_cases'])==6 and source['only_one_sequential_run']
        spec_path=(a.study/'report.json') if a.known_check else (a.study.parent/'run_spec.json')
        r['inputs'][str(spec_path)]=sha(spec_path)
        if not a.known_check:
            for name,digest in source['sources'].items():assert sha(repo/name)==sha(a.study.parent/'exact_sources'/name)==digest
            for name,digest in source['inputs'].items():assert sha(name)==digest
        versions={}
        for directory in directories:
            result=verify(directory)
            if a.known_check:
                original=next(c for c in old['cases'] if c['label']==directory.name)
                assert result['all_qualified'] and result['metrics']==original['metrics']
            r['cases'].append(dict(label=directory.name,**result))
            save(a.out/'report.json',r)
            print('REAL_CASE_AUDIT',directory.name,'solver',result['solver_qualified'],'fidelity',result['fidelity_qualified'],flush=True)
        names=set(source['sources'])|{'tools/waveform_file_real_v1/audit.py','tools/audit_waveform_file_real_v1.py'}
        for name in sorted(names):
            path=a.out/'exact_sources'/name;path.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,path);versions[name]=sha(path)
            if name in source['sources']:assert versions[name]==source['sources'][name]
        r.update(result='independent_waveform_file_real_known_auditor_verified' if a.known_check else 'independent_waveform_file_real_verified',
            verification_passed=True,all_qualified=all(c['all_qualified'] for c in r['cases']),sources=versions,
            no_C_or_hearing_or_sustained_qualification=True)
        save(a.out/'report.json',r)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
