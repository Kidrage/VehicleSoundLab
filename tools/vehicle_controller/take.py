"""Adopted controls at audio frames; no recorded audio in the synthesis recipe."""
from copy import deepcopy
from datetime import datetime,timezone
import json
import uuid
from pathlib import Path
from . import event_profiles,startup,event_policy as policy,dna_bank as dna,catalog_assets
from event_authoring.material_reviews import ensure_live_reference


def create(bridge,selection,control,event_overrides=None,startup_response=None,event_policy=None,dna_bank=None):
    bank=dna.supported(dna_bank,bridge.abi())
    overrides=event_profiles.validate_overrides(event_overrides)
    ensure_live_reference(overrides)
    response=startup.configuration(bridge,startup_response)
    configuration=policy.configuration(bridge,event_policy)
    event_identity=event_profiles.identity(bridge,overrides)
    value=dict(schema='vsl.source-controller-take/10' if bridge.abi()>=12 else 'vsl.source-controller-take/9' if bridge.abi()>=9 else 'vsl.source-controller-take/7' if bridge.abi()>=8 else 'vsl.source-controller-take/6' if bridge.abi()>=7 else 'vsl.source-controller-take/5',created=datetime.now(timezone.utc).isoformat(),stream_id=uuid.uuid4().hex,
                sample_rate=48000,catalog=deepcopy(bridge.catalog[selection]),bridge_sha256=bridge.sha256,
                voices_sha256=bridge.voices_sha256,
                event_bank_sha256=bridge.event_bank_sha256,
                event_overrides=overrides,event_effective_sha256=event_profiles.identity(bridge,overrides),
                startup_response=response,source_effective_sha256=startup.identity(bridge,response,event_identity,configuration,bank),
                initial=deepcopy(control),events=[],source_events=[],frames=0)
    if bridge.abi()>=7:value['event_policy']=configuration
    if bridge.abi()>=8:value['dna_bank']=bank
    return catalog_assets.attach(bridge,value)


def append(take,frame,control):
    previous=take['events'][-1]['control'] if take['events'] else take['initial']
    if previous!=control: take['events'].append(dict(frame=frame,control=deepcopy(control)))


def read(path,bridge):
    value=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    schema='vsl.source-controller-take/10' if bridge.abi()>=12 else 'vsl.source-controller-take/9' if bridge.abi()>=9 else 'vsl.source-controller-take/7' if bridge.abi()>=8 else 'vsl.source-controller-take/6' if bridge.abi()>=7 else 'vsl.source-controller-take/5'
    if value.get('schema')!=schema or value.get('sample_rate')!=48000: raise ValueError('行程格式不匹配，请使用对应冻结版本')
    catalog_assets.verify(bridge,value)
    if value.get('bridge_sha256')!=bridge.sha256: raise ValueError('行程使用另一版 C 引擎；请使用原版本回放')
    if value.get('voices_sha256')!=bridge.voices_sha256: raise ValueError('声源参数库已变化；请使用行程对应的冻结参数库')
    if value.get('event_bank_sha256')!=bridge.event_bank_sha256:raise ValueError('事件参数库不匹配')
    overrides=event_profiles.validate_overrides(value.get('event_overrides'))
    if value.get('event_effective_sha256')!=event_profiles.identity(bridge,overrides):raise ValueError('行程的自定义事件参数校验失败')
    response=startup.validate(value.get('startup_response'))
    configuration=policy.validate(value.get('event_policy')) if bridge.abi()>=7 else None
    if bridge.abi()>=8 and 'dna_bank' not in value:raise ValueError('行程缺少DNA身份字段')
    bank=dna.supported(value.get('dna_bank'),bridge.abi())
    if value.get('source_effective_sha256')!=startup.identity(bridge,response,event_profiles.identity(bridge,overrides),configuration,bank):
        raise ValueError('行程的启动响应、触发策略或完整声源身份校验失败')
    selection=value.get('catalog',{}).get('id')
    if not isinstance(selection,int) or not 0<=selection<len(bridge.catalog) or value['catalog']!=bridge.catalog[selection]: raise ValueError('音色目录不匹配')
    if not isinstance(value.get('frames'),int) or not 0<value['frames']<=48000*7200: raise ValueError('行程长度无效')
    last=-1
    for event in value.get('events',[]):
        frame=event.get('frame')
        if not isinstance(frame,int) or not last<=frame<value['frames']: raise ValueError('行程事件顺序或范围无效')
        last=frame
    return value


def save(path,value):
    target=Path(path);target.parent.mkdir(parents=True,exist_ok=True)
    temporary=target.with_suffix(target.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    temporary.replace(target)


def replay_block(engine,take,index,frames,solo=-1):
    pieces=[];notices=[];end=min(engine.frame+frames,take['frames']);events=take['events']
    while engine.frame<end:
        while index<len(events) and events[index]['frame']==engine.frame:
            engine.set(events[index]['control']);index+=1
        next_frame=min(end,events[index]['frame'] if index<len(events) else end)
        if next_frame<=engine.frame: raise ValueError('行程事件落后于音频时钟')
        pieces.append(engine.process(next_frame-engine.frame,solo))
        notices.extend(engine.last_events)
    # One host block may contain several native process calls. Preserve notices
    # from every piece, including a start before a later gain/control update.
    engine.last_events=notices
    return b''.join(pieces),index
