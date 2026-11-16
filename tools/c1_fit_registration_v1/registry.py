"""Exclusive canonical ledger and immutable paired claims; no fitting imports."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re


SCHEMA = 'vsl.c1-source-fit-registration/1'
FORBIDDEN = ('F3 Fifth First Early', 'F3 Fifth First Mid')


class RegistrationError(ValueError):
    pass


def normalized(label):
    if not isinstance(label, str) or not label.strip():
        raise RegistrationError('Invalid original label')
    return ' '.join(label.split()).casefold()


def key(label):
    return hashlib.sha256(normalized(label).encode('utf-8')).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2)+'\n').encode('utf-8')


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def read(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise RegistrationError('Missing or corrupt record: '+str(path)) from error
    if not isinstance(value, dict):
        raise RegistrationError('Record must be an object: '+str(path))
    return value


def exclusive(path, data):
    with Path(path).open('xb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


@contextmanager
def ledger_lock(root):
    """Keep the lock file as evidence; only its OS lock has a finite lifetime."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    stream = (root/'.registry.lock').open('a+b')
    if stream.seek(0, 2) == 0:
        stream.write(b'0')
        stream.flush()
    stream.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        stream.close()
        raise RegistrationError('Canonical registration ledger is locked') from error
    try:
        yield
    finally:
        stream.seek(0)
        if os.name == 'nt':
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


def validate(spec):
    if spec.get('schema') != SCHEMA or spec.get('state') != 'reserved_only':
        raise RegistrationError('Unsupported or corrupt registration')
    normalized(spec.get('original_label'))
    if spec.get('claim_key') != key(spec['original_label']):
        raise RegistrationError('Original-label claim key mismatch')
    ancestry = spec.get('ancestry')
    if not isinstance(ancestry, dict) or set(ancestry) != {'original_preparation_sha256', 'original_context_sha256'}:
        raise RegistrationError('Complete original source ancestry required')
    for value in [*ancestry.values(), spec.get('input_sha256')]:
        if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
            raise RegistrationError('Complete source hashes required')
    if not all(isinstance(spec.get(k), str) and spec[k] for k in
               ('source_identity', 'measurement_identity', 'canonical_claim', 'storage_claim')):
        raise RegistrationError('Explicit identities and both claim paths required')


def legacy_labels(roots):
    result = []
    for root in map(Path, roots):
        if not root.is_dir():
            raise RegistrationError('Missing legacy namespace: '+str(root))
        spec, report = read(root/'run_spec.json'), read(root/'report.json')
        if report.get('result') != 'failed':
            raise RegistrationError('Legacy namespace is not the preserved terminal failure')
        labels = []
        if spec.get('only_one_finite_case') is True:
            labels.extend(spec.get('declared_cases', []))
        elif spec.get('only_one_sequential_run') is not True:
            raise RegistrationError('Unknown legacy reservation semantics')
        # A terminated sequential run's declared_cases is its plan, not proof
        # that all planned cases were consumed. Actual attempts remain blocking.
        if report.get('current_case'):
            labels.append(report['current_case'])
        labels.extend(c['label'] for c in report.get('cases', []))
        for child in root.iterdir():
            if child.is_dir() and child.name != 'exact_sources':
                labels.append(child.name.removesuffix('_audit'))
        result.extend(dict(label=label, path=str(root)) for label in labels)
    return result


def claims(root):
    root = Path(root)
    if not root.exists():
        return []
    result = []
    for child in root.iterdir():
        if child.name == '.registry.lock' and child.is_file():
            continue
        if not child.is_dir() or child.is_symlink() or re.fullmatch('[0-9a-f]{64}', child.name) is None:
            raise RegistrationError('Unexpected ledger entry: '+str(child))
        spec = read(child/'run_spec.json')
        validate(spec)
        if child.name != spec['claim_key'] or child.resolve() not in (
                Path(spec['canonical_claim']).resolve(), Path(spec['storage_claim']).resolve()):
            raise RegistrationError('Claim path mismatch: '+str(child))
        result.append(spec)
    return result


def available(payload, canonical, storage, legacy_roots):
    label = normalized(payload['original_label'])
    if label in map(normalized, FORBIDDEN):
        raise RegistrationError('Never refit FirstEarly or FirstMid')
    for old in legacy_labels(legacy_roots):
        if normalized(old['label']) == label:
            raise RegistrationError('Already attempted in legacy E namespace: '+old['path'])
    for old in [*claims(canonical), *claims(storage)]:
        if normalized(old['original_label']) == label:
            raise RegistrationError('Already claimed in E or D by original label')
        if any(old['ancestry'][k] == v for k, v in payload['ancestry'].items()):
            raise RegistrationError('Original source ancestry already claimed under another label')
        if old['input_sha256'] == payload['input_sha256']:
            raise RegistrationError('Prepared input already claimed under another label')


def reserve(payload, canonical, storage, legacy_roots):
    canonical, storage = Path(canonical).resolve(), Path(storage).resolve()
    if canonical == storage or canonical.is_relative_to(storage) or storage.is_relative_to(canonical):
        raise RegistrationError('Independent canonical/storage ledgers required')
    token = key(payload['original_label'])
    e, d = canonical/token, storage/token
    spec = dict(payload, schema=SCHEMA, state='reserved_only', claim_key=token,
                canonical_claim=str(e), storage_claim=str(d))
    validate(spec)
    with ledger_lock(canonical):
        available(spec, canonical, storage, legacy_roots)
        # Every partial record deliberately survives an exception. A repeated
        # reservation cannot remove or overwrite either side to obtain a retry.
        e.mkdir()
        exclusive(e/'run_spec.json', encoded(spec))
        storage.mkdir(parents=True, exist_ok=True)
        d.mkdir()
        exclusive(d/'run_spec.json', encoded(spec))
        receipt = dict(schema='vsl.c1-source-fit-pair-receipt/1', claim_key=token,
                       registration_sha256=digest(e/'run_spec.json'), both_specs_identical=True)
        exclusive(e/'pair_receipt.json', encoded(receipt))
        exclusive(d/'pair_receipt.json', encoded(receipt))
        return verify_pair(e, d)


def verify_pair(e, d):
    e, d = Path(e).resolve(), Path(d).resolve()
    spec = read(e/'run_spec.json')
    validate(spec)
    if (Path(spec['canonical_claim']).resolve() != e or Path(spec['storage_claim']).resolve() != d
            or e == d or digest(e/'run_spec.json') != digest(d/'run_spec.json')):
        raise RegistrationError('Canonical/storage registration mismatch')
    receipt = read(e/'pair_receipt.json')
    if (receipt != read(d/'pair_receipt.json')
            or receipt != dict(schema='vsl.c1-source-fit-pair-receipt/1', claim_key=spec['claim_key'],
                               registration_sha256=digest(e/'run_spec.json'), both_specs_identical=True)):
        raise RegistrationError('Incomplete or corrupt paired receipt')
    return dict(spec=spec, registration_sha256=digest(e/'run_spec.json'),
                receipt_sha256=digest(e/'pair_receipt.json'), both_claims_verified=True)
