"""Per-engine event timing recipe; C owns eligibility, clocks and scheduling."""
import ctypes as C
import math

FIELDS=(
 ('afterfire_min_count','回火最少次数',1,4,1,1),
 ('afterfire_max_count','回火最多次数',1,4,1,3),
 ('afterfire_delay_seconds','收油后延迟 · s',0,.65,.001,.018),
 ('afterfire_interval_min_seconds','连发最短间隔 · s',.02,.65,.005,.095),
 ('afterfire_interval_max_seconds','连发最长间隔 · s',.02,.65,.005,.16),
 ('afterfire_repeat_gain','每次连发强度倍率',0,1.3,.01,.72),
 ('afterfire_probability','合格收油的触发概率',0,1,.05,1),
 ('afterfire_cooldown_seconds','两组回火冷却 · s',0,6.5,.05,0),
 ('shift_delay_seconds','换挡短声延迟 · s',0,.325,.001,.010),
 ('crank_delay_seconds','拖转纹理延迟 · s',0,.13,.001,.008))

class Policy(C.Structure):
    _fields_=[(key,C.c_uint if index<2 else C.c_double) for index,(key,*_) in enumerate(FIELDS)]

class Stats(C.Structure):
    _fields_=[(key,C.c_uint) for key in ('opportunities','bursts_attempted','unavailable','probability_skips','cooldown_skips')]

def defaults():return {key:default for key,*_,default in FIELDS}

def validate(value):
    if not isinstance(value,dict) or set(value)!={row[0] for row in FIELDS}:
        raise ValueError('事件触发配方必须包含完整的10个参数')
    result={}
    for index,(key,label,low,high,step,default) in enumerate(FIELDS):
        x=value[key]
        if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not low<=x<=high or index<2 and int(x)!=x:
            raise ValueError(f'{label}应在 {low}–{high} 之间'+('，且为整数' if index<2 else ''))
        result[key]=int(x) if index<2 else float(x)
    if result['afterfire_min_count']>result['afterfire_max_count']:raise ValueError('最少连发次数不能超过最多次数')
    if result['afterfire_interval_min_seconds']>result['afterfire_interval_max_seconds']:raise ValueError('最短间隔不能超过最长间隔')
    return result

def configuration(bridge,value=None):
    result=validate(bridge.event_policy_defaults if value is None else value)
    if bridge.abi()<7 and result!=validate(defaults()):raise ValueError('旧引擎不支持自定义触发配方；请使用V7')
    return result
