"""Portable authored DNA parameters; no audio, NumPy or runtime file dependency."""
from copy import deepcopy
import hashlib
import json
import math
import re
from pathlib import Path

SCHEMA='vsl.controller-dna-bank/1'
STATE_SCHEMA='vsl.controller-dna-bank/2'
STATES=('idle','power','overrun')


def describe(text):
    if not isinstance(text,str) or len(text)>2*1024**2:raise ValueError('DNA参数文本无效或过大')
    try:tokens=text.encode('ascii').decode('ascii').split()
    except UnicodeError:raise ValueError('DNA模型必须为ASCII参数文本') from None
    if len(tokens)<7 or tokens[0] not in ('VSL_SOUND_DNA','VSL_SUSTAIN_OSC'):
        raise ValueError('不支持的DNA模型')
    try:
        if any(re.fullmatch(r'\+?[0-9]+',x) is None for x in tokens[1:7]):raise ValueError()
        header=[int(x) for x in tokens[1:7]]
        version,rate,window,hop,h,k=header
        if (version,rate,window,hop)!=(1,48000,1024,256) or not 1<=h<=320 or not 0<=k<=16:
            raise ValueError()
        start=8 if tokens[0]=='VSL_SOUND_DNA' else 7
        numeric=tokens[7:] if start==8 else tokens[7:]
        if any(re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?',x) is None for x in numeric):raise ValueError()
        base=float(tokens[7]) if start==8 else 46.875
        if not math.isfinite(base) or not 5<=base<=1000 or h*base*1.1>21600:raise ValueError()
        if len(tokens)!=start+k+h*(21+4*k):raise ValueError()
        values=[float(x) for x in tokens[start:]]
        if any(not math.isfinite(x) or abs(x)>4 for x in values):raise ValueError()
        if any(abs(x)>.95 for x in values[:k]):raise ValueError()
        for i in range(h):
            if abs(values[k+i*(21+4*k)+4+4*k])>.95:raise ValueError()
    except (ValueError,IndexError,OverflowError):raise ValueError('DNA维度、频率覆盖或系数范围无效') from None
    return dict(base_hz=base,harmonics=h,components=k)


def _number(x,low,high,label):
    if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not low<=x<=high:
        raise ValueError(label+'超出范围')
    return float(x)


def _integer(x,low,high,label):
    if type(x) is not int or not low<=x<=high:raise ValueError(label+'必须为范围内整数')
    return x


def validate(value):
    if value is None:return None
    common={'schema','name','root_per_rpm','seed','align_orders','detail','anchors'}
    if (not isinstance(value,dict) or value.get('schema') not in (SCHEMA,STATE_SCHEMA) or
        set(value)!=(common|{'states','transition_seconds'} if value.get('schema')==STATE_SCHEMA else common)):
        raise ValueError('驾驶DNA包字段或版本不匹配')
    if not isinstance(value['name'],str) or not 1<=len(value['name'])<=100:raise ValueError('DNA名称需1–100字')
    _number(value['root_per_rpm'],1e-12,.1,'声学基频/RPM映射')
    _integer(value['seed'],1,2**64-1,'随机种子')
    _integer(value['align_orders'],0,32,'相位对齐阶数')
    _number(value['detail'],0,1,'DNA细节')
    anchors=value['anchors']
    if not isinstance(anchors,list) or not 1<=len(anchors)<=8:raise ValueError('需1–8个DNA锚点')
    last=0;harmonics=None
    for anchor in anchors:
        if not isinstance(anchor,dict) or set(anchor)!={'name','model','sha256','base_hz','harmonics','components'}:
            raise ValueError('DNA锚点字段不完整')
        if not isinstance(anchor['name'],str) or not 1<=len(anchor['name'])<=100:raise ValueError('锚点名称无效')
        info=describe(anchor['model'])
        if anchor['sha256']!=hashlib.sha256(anchor['model'].encode('ascii')).hexdigest():raise ValueError('DNA模型校验失败')
        if (any(type(anchor[k]) is not int or anchor[k]!=info[k] for k in ('harmonics','components')) or
            isinstance(anchor['base_hz'],bool) or anchor['base_hz']!=info['base_hz']):raise ValueError('DNA模型描述与参数不符')
        if info['base_hz']<=last or harmonics is not None and harmonics!=info['harmonics']:
            raise ValueError('锚点必须按基频递增，且分音数相同；不会自动截断分音')
        last=info['base_hz'];harmonics=info['harmonics']
    if value['schema']==STATE_SCHEMA:
        _number(value['transition_seconds'],.02,2,'状态过渡时间')
        states=value['states']
        if not isinstance(states,dict) or not states or set(states)-set(STATES):raise ValueError('状态库应包含怠速、加速或收油锚点')
        for anchors in states.values():
            candidate={k:deepcopy(value[k]) for k in common};candidate.update(schema=SCHEMA,anchors=anchors)
            donor=validate(candidate)
            if donor['anchors'][0]['harmonics']!=harmonics:raise ValueError('所有状态库分音数必须相同；不会截断分音')
    return deepcopy(value)


def with_states(bank,states,transition_seconds=.12):
    base=validate(bank)
    if base is None:raise ValueError('请先建立默认声纹')
    base={k:base[k] for k in ('schema','name','root_per_rpm','seed','align_orders','detail','anchors')}
    base['schema']=SCHEMA
    if states:base.update(schema=STATE_SCHEMA,states=deepcopy(states),transition_seconds=transition_seconds)
    return validate(base)


def supported(bank,abi):
    value=validate(bank)
    if value is not None and (abi<8 or value['schema']==STATE_SCHEMA and abi<9):
        raise ValueError('此冻结引擎不支持所选DNA状态库；状态库需要V9')
    return value


def banks(value):
    bank=validate(value)
    return [bank['anchors']]+[bank.get('states',{}).get(key,[]) for key in STATES]


def anchor(text,name):
    info=describe(text)
    return dict(name=name,model=text,sha256=hashlib.sha256(text.encode('ascii')).hexdigest(),**info)


def create(anchors,reference_rpm,name='自定义驾驶DNA',seed=48271,align_orders=12,detail=1.):
    if not isinstance(anchors,list) or not anchors:raise ValueError('请先加入DNA锚点')
    rpm=_number(reference_rpm,50,10000,'首锚点参考RPM')
    return validate(dict(schema=SCHEMA,name=name,root_per_rpm=anchors[0]['base_hz']/rpm,
        seed=seed,align_orders=align_orders,detail=detail,anchors=deepcopy(anchors)))


def read(path):
    path=Path(path)
    if path.suffix.lower()=='.model':
        return anchor(path.read_text(encoding='ascii'),path.stem[:100])
    return validate(json.loads(path.read_text(encoding='utf-8-sig')))


def digest(value):
    return hashlib.sha256(json.dumps(validate(value),sort_keys=True,separators=(',',':'),
        ensure_ascii=False,allow_nan=False).encode('utf-8')).hexdigest()


def coverage(value):
    bank=validate(value)
    if bank is None:return '目录声纹'
    a=bank['anchors'];ratio=bank['root_per_rpm']
    text=(f"{bank['name']} · {len(a)}锚点 · {a[0]['base_hz']/ratio:.0f}–{a[-1]['base_hz']/ratio:.0f} RPM默认参考范围\n"
        'RPM为人工映射；范围外为变调外推。')
    if bank['schema']==STATE_SCHEMA:
        labels={'idle':'怠速','power':'加速','overrun':'收油'}
        text+=' 状态：'+ ' / '.join(labels[k]+f" {len(bank['states'][k])}锚点" for k in STATES if k in bank['states'])
    else:text+=' 单状态不代表完整发动机标定。'
    return text
