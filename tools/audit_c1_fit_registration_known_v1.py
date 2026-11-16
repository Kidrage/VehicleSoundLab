"""Exercise paired-claim failures before touching actual source namespaces."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from c1_fit_registration_v1.registry import (
    RegistrationError, reserve, verify_pair, ledger_lock, encoded, key, SCHEMA)
from research_archive_v1 import save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', sources={}, successes=[], rejections=[], no_material_read=True)
    for name in ('tools/audit_c1_fit_registration_known_v1.py',
                 'tools/c1_fit_registration_v1/__init__.py', 'tools/c1_fit_registration_v1/registry.py',
                 'research/c1_fit_registration_v1_plan.json'):
        dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dest)
        r['sources'][name] = sha(dest)

    def layout(name):
        root = a.out/'fixtures'/name
        roots = root/'legacy_sequential', root/'legacy_single'
        for path in roots:
            path.mkdir(parents=True)
        save(roots[0]/'run_spec.json', dict(only_one_sequential_run=True,
            declared_cases=['F3 Fifth First Early', 'F3 Fifth First Mid', 'F3 Fifth First Late']))
        save(roots[0]/'report.json', dict(result='failed', current_case='F3 Fifth First Early', cases=[]))
        save(roots[1]/'run_spec.json', dict(only_one_finite_case=True, declared_cases=['F3 Fifth First Mid']))
        save(roots[1]/'report.json', dict(result='failed', current_case='F3 Fifth First Mid', cases=[]))
        (roots[0]/'F3 Fifth First Early').mkdir()
        (roots[0]/'F3 Fifth First Early_audit').mkdir()
        (roots[1]/'F3 Fifth First Mid').mkdir()
        payload = dict(original_label='F3 Fifth First Late',
            ancestry=dict(original_preparation_sha256='1'*64, original_context_sha256='2'*64),
            input_sha256='3'*64, source_identity='vsl.c1-22k-source-preparation/1',
            measurement_identity='vsl.c1-declared-objective/1')
        return root, root/'canonical', root/'storage', roots, payload

    def seed(e, d, payload, side):
        token = key(payload['original_label'])
        spec = dict(payload, schema=SCHEMA, state='reserved_only', claim_key=token,
                    canonical_claim=str((e/token).resolve()), storage_claim=str((d/token).resolve()))
        path = (e if side == 'E' else d)/token
        path.mkdir(parents=True)
        save(path/'run_spec.json', spec)
        return path

    def reject(name, expected, action):
        try:
            action()
        except RegistrationError as error:
            assert expected in str(error), (name, expected, str(error))
            r['rejections'].append(dict(name=name, expected=expected, actual=str(error)))
        else:
            raise AssertionError('Unsafe registration accepted: '+name)

    try:
        root, e, d, roots, payload = layout('success')
        pair = reserve(payload, e, d, roots)
        left, right = Path(pair['spec']['canonical_claim']), Path(pair['spec']['storage_claim'])
        # Independent byte/hash/JSON inspection, not the production pair verifier.
        first, second = (left/'run_spec.json').read_bytes(), (right/'run_spec.json').read_bytes()
        assert first == second
        spec = json.loads(first)
        receipt = json.loads((left/'pair_receipt.json').read_bytes())
        assert (left/'pair_receipt.json').read_bytes() == (right/'pair_receipt.json').read_bytes()
        assert receipt['registration_sha256'] == hashlib.sha256(first).hexdigest()
        assert spec['original_label'] == payload['original_label'] and spec['ancestry'] == payload['ancestry']
        assert spec['claim_key'] == hashlib.sha256(b'f3 fifth first late').hexdigest()
        assert not list(root.rglob('*.bin'))
        r['successes'].append(dict(name='paired_original_plan_does_not_mean_all_fitted',
            spec_sha256=hashlib.sha256(first).hexdigest(), independent_pair_bytes_and_hashes=True))

        for label in ('F3 Fifth First Early', 'F3 Fifth First Mid'):
            _, e, d, roots, payload = layout('forbidden_'+label.split()[-1])
            payload['original_label'] = label
            reject(label, 'Never refit', lambda: reserve(payload, e, d, roots))

        for side in ('E', 'D'):
            for kind in ('only', 'partial', 'corrupt'):
                _, e, d, roots, payload = layout(side+'_'+kind)
                path = seed(e, d, payload, side)
                if kind == 'partial':
                    # A crash after mkdir but before the exclusive spec write.
                    (path/'run_spec.json').rename(path/'preserved_interrupted_spec.json')
                elif kind == 'corrupt':
                    (path/'run_spec.json').write_text('{', encoding='utf-8')
                reject(side+'_'+kind, 'Already claimed' if kind == 'only' else 'Missing or corrupt',
                       lambda: reserve(payload, e, d, roots))

        for kind in ('ancestry_alias', 'input_alias', 'new_method', 'failed_attempt'):
            _, e, d, roots, payload = layout(kind)
            old = dict(payload, ancestry=dict(payload['ancestry']))
            expected = 'Already claimed'
            if kind == 'ancestry_alias':
                old['original_label'] = 'Renamed source'
                old['input_sha256'] = '4'*64
                expected = 'ancestry already claimed'
            elif kind == 'input_alias':
                old['original_label'] = 'Renamed source'
                old['ancestry'] = dict(original_preparation_sha256='4'*64, original_context_sha256='5'*64)
                expected = 'Prepared input already claimed'
            elif kind == 'new_method':
                old['source_identity'] = 'another-method-cannot-reset-original-label'
            path = seed(e, d, old, 'D')
            if kind == 'failed_attempt':
                save(path/'execution_report.json', dict(result='failed'))
            reject(kind, expected, lambda: reserve(payload, e, d, roots))

        for kind in ('legacy_current', 'legacy_directory'):
            _, e, d, roots, payload = layout(kind)
            if kind == 'legacy_current':
                save(roots[0]/'report.json', dict(result='failed', current_case=payload['original_label'], cases=[]))
            else:
                (roots[0]/payload['original_label']).mkdir()
            reject(kind, 'Already attempted', lambda: reserve(payload, e, d, roots))

        for kind in ('missing_receipt', 'altered_both_specs', 'altered_one_spec'):
            _, e, d, roots, payload = layout(kind)
            pair = reserve(payload, e, d, roots)
            left, right = Path(pair['spec']['canonical_claim']), Path(pair['spec']['storage_claim'])
            if kind == 'missing_receipt':
                (right/'pair_receipt.json').rename(right/'preserved_interrupted_receipt.json')
                expected = 'Missing or corrupt'
            else:
                for path in ((left, right) if kind == 'altered_both_specs' else (right,)):
                    body = json.loads((path/'run_spec.json').read_text(encoding='utf-8'))
                    body['input_sha256'] = '9'*64
                    (path/'run_spec.json').write_bytes(encoded(body))
                expected = 'corrupt paired receipt' if kind == 'altered_both_specs' else 'registration mismatch'
            reject(kind, expected, lambda: verify_pair(left, right))

        _, e, d, roots, payload = layout('held_lock')
        with ledger_lock(e):
            reject('held_lock', 'ledger is locked', lambda: reserve(payload, e, d, roots))
        assert not list(e.rglob('run_spec.json')) and not d.exists()
        assert len(r['rejections']) == 18
        r.update(result='c1_fit_registration_known_verified', verification_passed=True,
            independent_success_pair_inspection=True, rejection_count=18,
            no_actual_workspace_claims_or_factors=True)
        save(a.out/'report.json', r)
        print('C1_REGISTRATION_KNOWN', len(r['successes']), len(r['rejections']), flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
