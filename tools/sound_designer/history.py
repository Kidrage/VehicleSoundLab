"""Immutable authoring snapshots. Audio processing and C models stay unchanged."""
from datetime import datetime, timezone
import hashlib
import json
import uuid


def _path(folder, identity):
    if not isinstance(identity, str) or len(identity) != 32 or any(c not in '0123456789abcdef' for c in identity):
        raise ValueError('无效历史版本编号')
    return folder / 'history' / (identity + '.json')


def entries(folder):
    files = (folder / 'history').glob('*.json')
    return sorted(files, key=lambda p: p.stat().st_mtime_ns, reverse=True)


def checkpoint(folder, project, action):
    model = folder / 'base.model'
    payload = dict(project=project, base_model=model.read_text(encoding='ascii') if model.exists() else None)
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False)
    fingerprint = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    previous = entries(folder)
    if previous and json.loads(previous[0].read_text(encoding='utf-8'))['fingerprint'] == fingerprint:
        return previous[0].stem
    identity = uuid.uuid4().hex
    target = _path(folder, identity)
    target.parent.mkdir(exist_ok=True)
    value = dict(schema='vsl.sound-designer-history/1', id=identity,
                 created=datetime.now(timezone.utc).isoformat(timespec='microseconds'),
                 action=action, fingerprint=fingerprint, **payload)
    # Exclusive create: successful snapshots are never overwritten by later edits.
    temporary = target.with_suffix('.pending')
    with temporary.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
    temporary.rename(target)
    return identity


def listing(folder):
    result = []
    for file in entries(folder):
        value = json.loads(file.read_text(encoding='utf-8'))
        p = value['project']
        version = p.get('last_version') if not p.get('preview_stale') else None
        result.append(dict(id=value['id'], created=value['created'], action=value['action'], name=p['name'],
                           has_model=value['base_model'] is not None, preview_version=version))
    return result


def read(folder, identity):
    value = json.loads(_path(folder, identity).read_text(encoding='utf-8'))
    if value.get('schema') != 'vsl.sound-designer-history/1' or value.get('id') != identity:
        raise ValueError('历史版本格式无效')
    payload = dict(project=value['project'], base_model=value['base_model'])
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False)
    if hashlib.sha256(raw.encode('utf-8')).hexdigest() != value['fingerprint']:
        raise ValueError('历史版本校验失败')
    return value
