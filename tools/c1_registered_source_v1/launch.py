"""One irreversible-in-the-ledger launch intent; never delete partial attempts."""
from datetime import datetime, timezone
import os
from pathlib import Path
from c1_fit_registration_v1.registry import (
    RegistrationError, digest, encoded, exclusive, ledger_lock, read)


def begin(e, d):
    e, d = Path(e).resolve(), Path(d).resolve()
    with ledger_lock(e.parent):
        if any((root/'launch_intent.json').exists() for root in (e, d)):
            raise RegistrationError('Launch already consumed in E or D; no restart')
        if (e/'execution_spec.json').read_bytes() != (d/'execution_spec.json').read_bytes():
            raise RegistrationError('Paired execution spec mismatch')
        spec = read(e/'execution_spec.json')
        if spec.get('schema') != 'vsl.c1-registered-source-execution/1':
            raise RegistrationError('Explicit registered execution spec required')
        if Path(spec['output']).resolve() != (d/'run1').resolve() or Path(spec['output']).exists():
            raise RegistrationError('Execution output already exists or escaped the claim')
        value = dict(schema='vsl.c1-single-launch-intent/1', pid=os.getpid(),
            observed_utc=datetime.now(timezone.utc).isoformat(),
            execution_spec_sha256=digest(e/'execution_spec.json'),
            registration_sha256=spec['registration_sha256'], output=spec['output'], only_label=spec['only_label'])
        exclusive(e/'launch_intent.json', encoded(value))
        exclusive(d/'launch_intent.json', encoded(value))
        return value
