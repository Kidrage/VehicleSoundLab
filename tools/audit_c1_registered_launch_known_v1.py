"""Exercise exclusive launch consumption on synthetic claims, without fitting."""
import argparse
from pathlib import Path
import shutil
from c1_fit_registration_v1.registry import RegistrationError
from c1_registered_source_v1.launch import begin
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    r = dict(result='running', sources={}, cases=[], no_actual_claim_or_fit=True)
    for name in ('tools/audit_c1_registered_launch_known_v1.py', 'tools/c1_registered_source_v1/launch.py',
                 'tools/c1_fit_registration_v1/registry.py'):
        dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dest)
        r['sources'][name] = sha(dest)
    def layout(name):
        root = a.out/'fixtures'/name
        e, d = root/'E/claim', root/'D/claim'
        for path in (e, d):
            path.mkdir(parents=True)
            save(path/'execution_spec.json', dict(schema='vsl.c1-registered-source-execution/1',
                output=str((d/'run1').resolve()), registration_sha256='1'*64, only_label='known'))
        return e, d
    def reject(name, expected, e, d):
        try:
            begin(e, d)
        except RegistrationError as error:
            assert expected in str(error), (name, expected, str(error))
            r['cases'].append(dict(name=name, rejected=True, reason=str(error)))
        else:
            raise AssertionError('Unsafe launch accepted: '+name)
    try:
        e, d = layout('success')
        intent = begin(e, d)
        assert load(e/'launch_intent.json') == load(d/'launch_intent.json') == intent
        assert (e/'launch_intent.json').read_bytes() == (d/'launch_intent.json').read_bytes()
        assert not (d/'run1').exists()
        r['cases'].append(dict(name='success', same_intent_bytes=True))
        reject('repeat', 'already consumed', e, d)
        for side in ('E', 'D'):
            e, d = layout(side+'_partial')
            (e if side == 'E' else d).joinpath('launch_intent.json').write_bytes(b'{')
            reject(side+'_partial', 'already consumed', e, d)
        e, d = layout('output_exists')
        (d/'run1').mkdir()
        reject('output_exists', 'output already exists', e, d)
        e, d = layout('different_spec')
        value = load(d/'execution_spec.json')
        value['registration_sha256'] = '2'*64
        save(d/'execution_spec.json', value)
        reject('different_spec', 'spec mismatch', e, d)
        e, d = layout('escaped_output')
        for root in (e, d):
            value = load(root/'execution_spec.json')
            value['output'] = str(a.out/'unrelated')
            save(root/'execution_spec.json', value)
        reject('escaped_output', 'escaped the claim', e, d)
        r.update(result='c1_registered_launch_known_verified', verification_passed=True,
            successes=1, rejected=6, source_fitting_never_called=True)
        save(a.out/'report.json', r)
        print('C1_LAUNCH_KNOWN', 1, 6, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
