"""New-method terminal identity; never admit it under the old six-case schema."""
from pathlib import Path
import numpy as np
from research_archive_v1 import load, sha


def terminal(case, audit, *, repo, known=False):
    case, audit, repo = map(Path, (case, audit, repo))
    info, proof = load(case/'report.json'), load(audit)
    inputs = {str(path): sha(path) for path in (case/'report.json', case/'capture.npz', audit)}
    binding = case.parent/('report.json' if known else 'run_spec.json')
    if proof.get('inputs', {}).get(str(binding)) != sha(binding):
        raise ValueError('Immutable new-method source/spec binding differs from independent audit')
    source = load(binding)
    if known:
        if (proof.get('result') != 'independent_locked_source_known_verified'
                or not proof.get('all_qualified') or len(proof.get('cases', [])) != 4
                or info.get('result') != 'locked_source_fit_case_measured'
                or source.get('result') != 'locked_source_fit_known_measured'
                or proof.get('producer_sha256') != sha(binding)):
            raise ValueError('Complete independent new-source control qualification required')
        control = next((row for row in proof['cases'] if row['label'] == case.name), None)
        if control is None or not control.get('all_qualified') or not control.get('complete_audit_file'):
            raise ValueError('Nonzero control missing from independent complete equation verification')
        for path in (case/'report.json', case/'capture.npz'):
            if proof['inputs'].get(str(path)) != sha(path):
                raise ValueError('Independent control input digest differs: '+str(path))
        complete = audit.parent/control['complete_audit_file']
        inputs[str(complete)] = sha(complete)
        row = load(complete)
    else:
        if (proof.get('result') != 'independent_locked_source_real_verified'
                or not proof.get('verification_passed')
                or info.get('result') != 'locked_source_real_case_measured'
                or source.get('schema') != 'vsl.locked_source_real_spec/1'
                or source.get('declared_cases') != [case.name]
                or not source.get('only_one_finite_case')
                or case.name == 'F3 Fifth First Early'):
            raise ValueError('One terminal independently verified new-method real case required')
        row = proof.get('case', {})
    if row.get('result') != 'independent_locked_source_case_verified' or not row.get('verification_passed'):
        raise ValueError('Independent complete mathematical case verification required')
    if row.get('producer_sha256') != sha(case/'report.json'):
        raise ValueError('Case report differs from independently audited report')
    if row.get('capture_sha256') != info.get('capture_sha256') or sha(case/'capture.npz') != row['capture_sha256']:
        raise ValueError('Capture differs from independently audited capture')
    for flag in ('solver_qualified', 'fidelity_qualified'):
        if row.get(flag) != info.get(flag): raise ValueError('Independent qualification flag mismatch')
    for name, wanted in source['sources'].items():
        if sha(repo/name) != wanted or sha(case.parent/'exact_sources'/name) != wanted:
            raise ValueError('Frozen new-method extraction source changed: '+name)
    for path, wanted in source.get('inputs', {}).items():
        if sha(path) != wanted: raise ValueError('Frozen new-method extraction input changed: '+path)
    inputs[str(binding)] = sha(binding)
    with np.load(case/'capture.npz') as saved: z = {name: saved[name] for name in saved.files}
    if (z['audio'].ndim != 2 or z['audio'].shape[1] != 2 or z['wave'].shape != z['audio'].shape
            or not np.array_equal(z['audio'][2048:-2048], z['target'])
            or z['metric_target'].shape != z['target'].shape
            or any(not np.isfinite(z[name]).all() for name in ('audio', 'wave', 'target', 'metric_target', 'fitted'))):
        raise ValueError('Complete finite new audio, target, legacy calibration and fitted wave required')
    if not known:
        if not np.array_equal(z['orders'], np.arange(1, 289)):
            raise ValueError('Every original288order required for real diagnostics')
        prepared = Path(info['prepared_file'])
        if sha(prepared) != info['prepared_sha256'] or str(prepared) not in source['inputs']:
            raise ValueError('Frozen explicit calibration preparation changed')
        with np.load(prepared) as saved:
            for name in saved.files:
                if not np.array_equal(saved[name], z[name]):
                    raise ValueError('Audited preparation differs from capture: '+name)
        inputs[str(prepared)] = sha(prepared)
    return z, dict(label=case.name, known_control=known,
        method='sinc128 new audio fitted with explicit unchanged legacy metric_target',
        case_report_sha256=sha(case/'report.json'), capture_sha256=sha(case/'capture.npz'),
        math_audit_sha256=sha(audit), binding_file=str(binding), binding_sha256=sha(binding),
        solver_qualified=info['solver_qualified'], fidelity_qualified=info['fidelity_qualified'],
        existing_weighted_metrics=info['metrics'], inputs=inputs)
