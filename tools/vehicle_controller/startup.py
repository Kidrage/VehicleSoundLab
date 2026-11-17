"""Startup response contract; UI never integrates RPM or lifecycle time."""
import ctypes as C
import hashlib
import json
import math

# Same units and limits as profiles/lifecycle.c; native C validates again.
FIELDS=(
    ('crank_seconds','拖转时长 · s',.05,6.5),
    ('crank_rpm','拖转目标 · RPM',50,780),
    ('crank_tau','拖转响应时间 · s',.005,1.3),
    ('catch_rise_seconds','接火上升时长 · s',.025,1.95),
    ('catch_settle_seconds','冲转回落时长 · s',.05,5.2),
    ('flare_rpm','冲转峰值 · RPM',500,6500),
    ('combustion_seconds','燃烧建立时长 · s',.005,2.6),
    ('stopping_seconds','停机时长 · s',.05,6.5),
    ('stopping_tau','停机衰减时间 · s',.01,2.6))


class Response(C.Structure):
    _fields_=[(key,C.c_double) for key,*_ in FIELDS]


def validate(value):
    if not isinstance(value,dict) or set(value)!={row[0] for row in FIELDS}:
        raise ValueError('启动响应必须包含完整的9个参数')
    result={}
    for key,label,low,high in FIELDS:
        x=value[key]
        if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not low<=x<=high:
            raise ValueError(f'{label}应在 {low}–{high} 之间')
        result[key]=float(x)
    if result['combustion_seconds']>result['catch_rise_seconds']+result['catch_settle_seconds']:
        raise ValueError('燃烧建立时长不能超过接火上升与回落的总时长')
    return result


def configuration(bridge,value=None):
    return validate(bridge.startup_defaults if value is None else value)


def identity(bridge,value,event_identity,event_policy=None,dna_bank=None):
    doc=dict(bridge_sha256=bridge.sha256,voices_sha256=bridge.voices_sha256,
             event_effective_sha256=event_identity,startup_response=configuration(bridge,value))
    if bridge.abi()>=9:doc['catalog_assets_sha256']=bridge.catalog_assets_sha256
    if bridge.abi()>=7:
        from .event_policy import configuration as configure_policy
        doc['event_policy']=configure_policy(bridge,event_policy)
    if bridge.abi()>=8:
        from .dna_bank import digest
        doc['dna_bank_sha256']=digest(dna_bank)
    return hashlib.sha256(json.dumps(doc,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
