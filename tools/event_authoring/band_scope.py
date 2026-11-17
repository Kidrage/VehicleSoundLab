"""Explicit authoring frequency scope; this is not physical source separation."""
import math


def normalize(value=None):
    if value is None:
        return {'mode': 'full'}
    if not isinstance(value, dict):
        raise ValueError('分析频带必须为对象')
    if value.get('mode') == 'full' and set(value) == {'mode'}:
        return {'mode': 'full'}
    if value.get('mode') != 'band' or set(value) != {'mode', 'low_hz', 'high_hz'}:
        raise ValueError('分析频带格式无效')
    low, high = value['low_hz'], value['high_hz']
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
           for v in (low, high)) or not 60 <= low < high <= 14000 or high-low < 150:
        raise ValueError('分析频带需在60–14000 Hz内，宽度至少150 Hz')
    return {'mode': 'band', 'low_hz': float(low), 'high_hz': float(high)}


def edges(scope, original):
    scope = normalize(scope)
    if scope['mode'] == 'full':
        return original
    low, high = scope['low_hz'], scope['high_hz']
    return tuple((max(low, lo), min(high, hi)) for lo, hi in original
                 if max(low, lo) < min(high, hi))


def mask(frequency, scope):
    scope = normalize(scope)
    if scope['mode'] == 'full':
        return frequency >= 0
    return (frequency >= scope['low_hz']) & (frequency < scope['high_hz'])


def admission(observation):
    return observation.get('scoped_event_to_background_db', observation['event_to_background_db'])
