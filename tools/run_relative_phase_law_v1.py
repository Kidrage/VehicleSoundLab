"""Known controls, then read-only diagnostics of six already-saved stereo laws."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


FACTOR_KEYS = ('scores', 'pc', 'residual', 'basis', 'rho', 'residual_std', 'residual_rho', 'lags')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'out'): p.add_argument('--'+key, type=Path, required=True)
    p.add_argument('--stage', choices=('known', 'real'), required=True)
    for key in ('known', 'known-audit'): p.add_argument('--'+key, type=Path)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from relative_phase_law_v1.measure import assess
    from relative_phase_law_v1.controls import controls
    from c1_registered_source_v1.binding import protected
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    report = dict(result='running', stage=a.stage, cases=[], sources={}, inputs={}, known_errors={})
    def check(name,actual,expected,scale):
        actual,expected = np.asarray(actual),np.asarray(expected)
        assert actual.shape == expected.shape, name
        value = float(np.max(abs(actual-expected)))/max(float(scale),1e-300)
        report['known_errors'][name] = value
        if not np.isfinite(value) or value > 2e-11: raise ValueError((name,value))
    def packet(label, arrays, rows, groups, meta):
        folder = a.out/label; folder.mkdir()
        np.savez_compressed(folder/'factors.npz', **{k:v for k,v in arrays.items()
            if k in FACTOR_KEYS or k.startswith('known_')})
        digest = lambda v:hashlib.sha256(np.ascontiguousarray(v).tobytes()).hexdigest()
        return dict(label=label, factors_sha256=sha(folder/'factors.npz'), metadata=meta,
            rows=rows, groups=groups, all_matrix_sha256={k:digest(v) for k,v in arrays.items() if k.startswith('lag') and k!='lags'})
    try:
        protected(a.workspace,repo)
        for name in ('research/relative_phase_law_v1_plan.json', 'tools/run_relative_phase_law_v1.py',
            'tools/audit_relative_phase_law_v1.py', 'tools/relative_phase_law_v1/__init__.py',
            'tools/relative_phase_law_v1/measure.py', 'tools/relative_phase_law_v1/controls.py',
            'tools/relative_phase_law_v1/audit.py', 'tools/research_archive_v1.py'):
            dest = a.out/'exact_sources'/name; dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,dest); report['sources'][name] = sha(dest)
        lags = load(repo/'research/relative_phase_law_v1_plan.json')['lags']
        if a.stage == 'known':
            arrays,rows,groups,meta,proof = controls(check)
            report['cases'].append(packet('known',arrays,rows,groups,meta))
            report.update(known=proof,result='relative_phase_law_known_controls_passed')
        else:
            assert a.known and a.known_audit
            known,proof = load(a.known/'report.json'),load(a.known_audit/'report.json')
            assert known['result'] == 'relative_phase_law_known_controls_passed' and proof['verification_passed']
            assert proof['producer_sha256'] == sha(a.known/'report.json')
            assert known['sources'] == report['sources']
            report['inputs'].update({str(p):sha(p) for p in (a.known/'report.json',a.known_audit/'report.json')})
            root = a.workspace/'references/analysis/relative_phase_v1'
            source,source_audit = load(root/'real1/report.json'),load(root/'real_audit2/report.json')
            assert source['result'] == 'six_source_relative_phase_evidence_ready' and len(source['cases']) == 6
            assert source_audit['result'] == 'independent_relative_phase_audit_passed'
            assert source_audit['producer_sha256'] == sha(root/'real1/report.json')
            for path in (root/'real1/report.json',root/'real_audit2/report.json'):
                report['inputs'][str(path)] = sha(path)
            for name,digest in source['sources'].items(): assert sha(repo/name) == digest
            report['existing_profile_producer_sources'] = source['sources']
            for row in source['cases']:
                folder = root/'real1'/row['label']
                for name,digest in (('profile.npz',row['profile_sha256']),('training.npz',row['training_sha256'])):
                    assert sha(folder/name) == digest
                    report['inputs'][str(folder/name)] = digest
                with np.load(folder/'profile.npz') as f: model = {k:f[k] for k in f.files}
                with np.load(folder/'training.npz') as f: train = {k:f[k] for k in f.files}
                arrays,rows,groups,meta = assess(model,train,lags)
                result = packet(row['label'],arrays,rows,groups,meta)
                result.update(root_hz=row['root_hz'],physical_lag_seconds_not_identified=True)
                report['cases'].append(result)
                save(a.out/'report.json',report)
                print('READ_ONLY_LAW',row['label'],'lag1_error',rows[1]['model_error_over_C0'],
                    'lag1_skew',rows[1]['observed_skew_over_C0'],flush=True)
            report['result'] = 'six_saved_relative_phase_laws_measured_without_training'
        report.update(no_refit_new_training_audio_C_default_driver_room_or_hearing_change=True,
            new_C1_source_eligible_for_statistics=False, no_audible_or_physical_cause_claim=True,
            lag_units='sequence steps; no source physical-time equivalence asserted',
            full_goal='ACTIVE', full_matrices_bound_by_SHA256_and_exact_saved_factors=True)
        save(a.out/'report.json',report)
        print(report['result'],flush=True)
    except BaseException as error:
        report.update(result='failed',error=repr(error));save(a.out/'report.json',report);raise


if __name__ == '__main__': main()
