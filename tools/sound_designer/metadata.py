"""Shared authoring labels; tags describe input, never infer physical states."""

STATES = ('steady', 'idle', 'acceleration', 'deceleration', 'blip', 'startup', 'custom')
VIEWPOINTS = ('exterior', 'cabin', 'engine', 'unspecified')


def fields(data, previous=None):
    previous = previous or {}
    result = {key: data.get(key, previous.get(key, default)) for key, default in
              (('name', '未命名音色'), ('state', 'steady'), ('viewpoint', 'exterior'))}
    if not isinstance(result['name'], str) or not result['name'].strip() or len(result['name']) > 100:
        raise ValueError('音色名称需1–100个字符')
    if result['state'] not in STATES:
        raise ValueError('声音状态需为：' + ', '.join(STATES))
    if result['viewpoint'] not in VIEWPOINTS:
        raise ValueError('录音视角需为：' + ', '.join(VIEWPOINTS))
    return result
