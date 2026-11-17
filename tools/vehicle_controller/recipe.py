"""Portable controls + event overrides, bound to the exact source assets."""
from copy import deepcopy
from . import event_profiles,startup,event_policy as policy,dna_bank as dna,catalog_assets
from event_authoring.material_reviews import ensure_live_reference


def create(bridge,selection,control,mode,overrides,startup_response=None,event_policy=None,dna_bank=None):
    bank=dna.supported(dna_bank,bridge.abi())
    profiles=event_profiles.validate_overrides(overrides)
    ensure_live_reference(profiles)
    response=startup.configuration(bridge,startup_response)
    configuration=policy.configuration(bridge,event_policy)
    event_identity=event_profiles.identity(bridge,profiles)
    value=dict(schema='vsl.source-controller-preset/9' if bridge.abi()>=12 else 'vsl.source-controller-preset/8' if bridge.abi()>=9 else 'vsl.source-controller-preset/6' if bridge.abi()>=8 else 'vsl.source-controller-preset/5' if bridge.abi()>=7 else 'vsl.source-controller-preset/4',catalog=selection,control=deepcopy(control),mode=mode,
        startup_response=response,source_effective_sha256=startup.identity(bridge,response,event_identity,configuration,bank),
        event_overrides=profiles,bridge_sha256=bridge.sha256,voices_sha256=bridge.voices_sha256,
        event_bank_sha256=bridge.event_bank_sha256,event_effective_sha256=event_profiles.identity(bridge,profiles))
    if bridge.abi()>=7:value['event_policy']=configuration
    if bridge.abi()>=8:value['dna_bank']=bank
    return catalog_assets.attach(bridge,value)


def validate(bridge,value):
    expected=('vsl.source-controller-preset/9',) if bridge.abi()>=12 else ('vsl.source-controller-preset/8',) if bridge.abi()>=9 else ('vsl.source-controller-preset/6',) if bridge.abi()>=8 else ('vsl.source-controller-preset/5',) if bridge.abi()>=7 else ('vsl.source-controller-preset/3','vsl.source-controller-preset/4')
    if value.get('schema') not in expected:raise ValueError('配方版本不匹配；请使用对应冻结引擎，不自动迁移触发策略')
    catalog_assets.verify(bridge,value)
    profiles=event_profiles.validate_overrides(value.get('event_overrides'))
    ensure_live_reference(profiles)
    if any(value.get(key)!=expected for key,expected in [
        ('bridge_sha256',bridge.sha256),('voices_sha256',bridge.voices_sha256),
        ('event_bank_sha256',bridge.event_bank_sha256),('event_effective_sha256',event_profiles.identity(bridge,profiles))]):
        raise ValueError('配方引擎、参数库或自定义事件身份不匹配；请使用对应冻结版本')
    if bridge.abi()>=8 and 'dna_bank' not in value:raise ValueError('配方缺少DNA身份字段')
    bank=dna.supported(value.get('dna_bank'),bridge.abi())
    if value.get('schema') in ('vsl.source-controller-preset/4','vsl.source-controller-preset/5','vsl.source-controller-preset/6','vsl.source-controller-preset/8','vsl.source-controller-preset/9'):
        response=startup.validate(value.get('startup_response'))
        configuration=policy.validate(value.get('event_policy')) if bridge.abi()>=7 else None
        if value.get('source_effective_sha256')!=startup.identity(bridge,response,event_profiles.identity(bridge,profiles),configuration,bank):
            raise ValueError('配方的启动响应、触发策略或完整声源身份不匹配')
    return profiles
