"""Diagnose one audited real terminal case, or the three existing known controls."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','math-audit','meter-study','meter-audit','out'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--known-check',action='store_true')
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from extraction_sound_v1.consume import consume,terminal
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',cases=[],sources={},guard_rejections=[],inputs={})
    try:
        names=['tools/run_extraction_sound_cases_v2.py','tools/audit_extraction_sound_cases_v2.py',
            'research/extraction_sound_v2_plan.json']
        names.extend(p.relative_to(repo).as_posix() for p in (repo/'tools/extraction_sound_v1').glob('*.py'))
        for name in names:
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        audits=load(a.math_audit)
        if a.known_check:
            assert audits['result']=='independent_waveform_file_real_known_auditor_verified'
            cases=[a.study/c['label'] for c in audits['cases']]
            assert len(cases)==3
        else:cases=[a.study]
        for case in cases:
            output=a.out/case.name
            result=consume(case,a.math_audit,output,repo=repo,meter_study=a.meter_study,meter_audit=a.meter_audit,known=a.known_check)
            r['cases'].append(dict(label=case.name,report=case.name+'/report.json',sha256=sha(output/'report.json'),
                solver_qualified=result['source']['solver_qualified'],fidelity_qualified=result['source']['fidelity_qualified']))
            save(a.out/'report.json',r)
            print('SOUND_CASE',case.name,'target/whole completed',flush=True)
        if a.known_check:
            bad=a.out/'guards';bad.mkdir()
            # Actual archived controls and actual independent audit are used;
            # no artificial mathematical pass records are accepted.
            for name,change in (
                ('verification',lambda proof:proof.update(verification_passed=False)),
                ('kind',lambda proof:proof.update(result='running')),
                ('case_hash',lambda proof:proof['cases'][0].update(producer_sha256='0'*64)),
                ('capture_hash',lambda proof:proof['cases'][0].update(capture_sha256='0'*64)),
                ('qualification_flag',lambda proof:proof['cases'][0].update(solver_qualified=False)),
                ('spec_binding',lambda proof:proof['inputs'].update({str(a.study/'report.json'):'0'*64})),
            ):
                proof=load(a.math_audit);change(proof);path=bad/(name+'.json');save(path,proof)
                try:terminal(cases[0],path,repo=repo,known=True)
                except ValueError as error:r['guard_rejections'].append(dict(control=name,reason=str(error)))
                else:raise AssertionError('Corrupted verification was accepted: '+name)
            assert len(r['guard_rejections'])==6
        r.update(result='extraction_sound_known_cases_measured' if a.known_check else 'extraction_sound_real_case_measured',
            no_source_fit_restart_or_C_or_hearing_change=True)
        save(a.out/'report.json',r)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
