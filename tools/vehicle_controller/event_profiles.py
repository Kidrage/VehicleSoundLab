"""Per-engine authored event overrides and deterministic recipe identity."""
from copy import deepcopy
import hashlib
import json
from event_authoring.contract import KINDS,validate


def document(value):
    if not isinstance(value,dict):raise ValueError('事件参数必须是JSON对象')
    doc=value.get('document') if value.get('schema')=='vsl.event-design/1' else value
    if not isinstance(doc,dict) or doc.get('schema') not in ('vsl.event-profile/1','vsl.event-profile/2','vsl.event-profile/3','vsl.event-profile/4') or doc.get('kind') not in KINDS:
        raise ValueError('请选择事件设计器导出的参数JSON')
    validate(doc['parameters'])
    if not doc['parameters']['modes'] and not doc['parameters']['bands']:raise ValueError('导入事件缺少发声成分')
    return deepcopy(doc)


def validate_overrides(value):
    if value is None:return {}
    if not isinstance(value,dict) or set(value)-set(KINDS):raise ValueError('事件覆盖表无效')
    result={key:document(doc) for key,doc in value.items()}
    if any(doc['kind']!=key for key,doc in result.items()):raise ValueError('事件覆盖表类型不匹配')
    return result


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest()


def identity(bridge,overrides):
    return digest(dict(compiled_bank_sha256=bridge.event_bank_sha256,overrides=validate_overrides(overrides)))
