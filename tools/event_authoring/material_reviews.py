"""Human reference decisions for new live use; historical audio stays reproducible."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path


def decisions():
    path = Path(__file__).resolve().parents[2]/'research/material_review_decisions.json'
    value = json.loads(path.read_text(encoding='utf-8'))
    if value.get('schema') != 'vsl.material-review-decisions/1':
        raise ValueError('素材审阅记录格式不匹配')
    return value['decisions']


def parameter_digest(parameters):
    return hashlib.sha256(json.dumps(parameters, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def rejection(value):
    if not isinstance(value, dict):
        return None
    doc = value.get('document') if value.get('schema') == 'vsl.event-design/1' else value
    if not isinstance(doc, dict):
        return None
    provenance = doc.get('provenance') or {}
    for row in decisions():
        if row['decision'] != 'reject_reference' or row['kind'] != doc.get('kind'):
            continue
        source = row['source']
        first, last = provenance.get('first_frame'), provenance.get('last_frame')
        overlap = (provenance.get('sha256') == source['sha256'] and
            type(first) is int and type(last) is int and
            first < source['last_frame'] and last > source['first_frame'])
        identical = isinstance(doc.get('parameters'), dict) and parameter_digest(doc['parameters']) in row.get('parameter_sha256', [])
        if overlap or identical:
            return deepcopy(row)
    return None


def ensure_live_reference(overrides):
    for kind, doc in (overrides or {}).items():
        row = rejection(doc)
        if row:
            raise ValueError('该素材已被排除作为回火参考：'+row['reason']+
                '。请移除该事件或使用已清理的配方；历史行程仍可原样回放。')


def without_rejected(overrides):
    return {kind: deepcopy(doc) for kind, doc in (overrides or {}).items() if rejection(doc) is None}
