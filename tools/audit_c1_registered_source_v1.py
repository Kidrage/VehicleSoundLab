"""Independent terminal audit of the one concretely registered extraction."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    from c1_registered_source_v1.binding import execution
    from c1_registered_source_v1.complete import verify
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    r = dict(result='running', sources={}, inputs={})
    try:
        pair, spec = execution(a.workspace, repo)
        e, d = Path(pair['spec']['canonical_claim']), Path(pair['spec']['storage_claim'])
        assert a.study.resolve() == Path(spec['output']).resolve()
        assert (e/'launch_intent.json').read_bytes() == (d/'launch_intent.json').read_bytes()
        intent = load(e/'launch_intent.json')
        assert intent['execution_spec_sha256'] == sha(e/'execution_spec.json')
        info = load(a.study/'report.json')
        assert info['execution_spec_sha256'] == intent['execution_spec_sha256']
        assert info['pid'] == intent['pid'] and info['label'] == spec['only_label']
        assert info['measurement_identity'] == spec['measurement_identity']
        r['sources'].update(spec['source_closure'])
        r['inputs'].update(spec['input_closure'])
        r['inputs'][str(e/'execution_spec.json')] = sha(e/'execution_spec.json')
        r['inputs'][str(e/'launch_intent.json')] = sha(e/'launch_intent.json')
        case = verify(a.study)
        assert case['verification_passed']
        r.update(result='independent_c1_registered_source_verified', verification_passed=True,
            case=case, all_qualified=case['all_qualified'], only_registered_case=True,
            source_fidelity_requires_native_diagnostics=True, eligible_for_later_source_statistics=False,
            no_sustained_or_C_or_hearing_qualification=True)
        save(a.out/'report.json', r)
        print('C1_REAL_TERMINAL_AUDIT', case['solver_qualified'], case['fidelity_qualified'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
