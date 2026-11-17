"""Assemble existing startup/event/control contracts into a stopped V9 preset."""
from copy import deepcopy
from pathlib import Path
from event_authoring.contract import KINDS
from event_authoring.native import controls as audition_controls
from event_authoring.band_scope import normalize
from vehicle_controller import startup, event_policy, event_profiles, recipe, dna_bank
from vehicle_controller import dna_character
from vehicle_controller.native import Bridge, Engine
from research_archive_v1 import sha, load

EVENT_LABELS = ('啮合', '拖转', '接火', '收油回火', '换挡短声', '脱开', '停机末响')
LAYERS = (('mechanical_gain', 'DNA · 机械特征'),)
RETIRED_LAYERS = {'intake_gain','air_gain','road_gain','wind_gain'}
MACROS = (('gain', '事件总量', 0, 1.3, .01), ('pitch', '事件音高', .5, 2.6, .01),
          ('decay', '事件时长', .25, 5.2, .01), ('texture', '事件纹理', 0, 2.6, .01))


def event_id(value):
    if not isinstance(value, str) or len(value) != 32 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('无效事件工程编号')
    return value


def validate(value):
    if not isinstance(value, dict) or set(value) not in ({'startup','policy','events','layers'},{'startup','policy','events','layers','dna'}):
        raise ValueError('整车参数需包含启动、触发策略、事件及辅助层')
    result = dict(startup=startup.validate(value['startup']), policy=event_policy.validate(value['policy']))
    events = value['events']
    if not isinstance(events, dict) or set(events) != {'enabled', 'projects', 'levels', *(r[0] for r in MACROS)}:
        raise ValueError('整车事件字段不完整')
    if type(events['enabled']) is not bool:
        raise ValueError('自动事件开关必须是布尔值')
    if not isinstance(events['projects'], dict) or set(events['projects']) != set(KINDS):
        raise ValueError('需为七种事件分别指定工程或留空')
    for project in events['projects'].values():
        if project is not None: event_id(project)
    if not isinstance(events['levels'], list) or len(events['levels']) != 7:
        raise ValueError('事件电平需七项')
    for level in events['levels']: dna_bank._number(level, 0, 1.3, '事件电平')
    for key, label, low, high, _ in MACROS: dna_bank._number(events[key], low, high, label)
    result['events'] = deepcopy(events)
    layers = value['layers']
    if not isinstance(layers, dict) or set(layers) not in ({k for k, _ in LAYERS},{k for k, _ in LAYERS}|RETIRED_LAYERS):
        raise ValueError('辅助层参数不完整')
    if any(layers.get(key,0)!=0 for key in RETIRED_LAYERS):raise ValueError('旧辅助模板已退役；请先将其电平清零，原冻结版仍可回放旧配方')
    for key, label in LAYERS: dna_bank._number(layers[key], 0, 1.3, label)
    result['layers'] = {key:layers[key] for key,_ in LAYERS}
    result['dna'] = dna_character.validate(value.get('dna',dna_character.defaults()))
    return result


class VehicleSystem:
    def __init__(self, workspace):
        self.workspace = workspace
        self.events = workspace.root/'events'

    def choices(self):
        result = []
        for path in sorted(self.events.glob('*/project.json'), key=lambda p: p.stat().st_mtime_ns, reverse=True):
            p = load(path)
            if not p.get('document'): continue
            document = event_profiles.document(p['document'])
            scope = normalize(document.get('source_job', {}).get('analysis_scope'))
            result.append(dict(id=path.parent.name, name=p['name'], kind=document['kind'],
                viewpoint=p.get('viewpoint', 'unspecified'), band_limited=scope['mode'] == 'band',
                physical_identity_confirmed=document.get('physical_identity_confirmed') is True))
        return result

    def metadata(self):
        bridge = Bridge(self.workspace.repo)
        defaults = dict(startup=bridge.startup_defaults, policy=bridge.event_policy_defaults,
            events=dict(enabled=False, projects=dict.fromkeys(KINDS), levels=[1.]*7, gain=.3, pitch=1., decay=1., texture=1.),
            layers={key: 0. for key, _ in LAYERS},dna=dna_character.defaults())
        return dict(defaults=validate(defaults), startup_fields=startup.FIELDS,
            policy_fields=event_policy.FIELDS, macro_fields=MACROS, layer_fields=LAYERS,
            dna_fields=dna_character.FIELDS,dna_states=dna_character.STATES,
            kinds=[dict(key=k, label=label) for k, label in zip(KINDS, EVENT_LABELS)], projects=self.choices())

    def compile(self, bank, settings):
        settings = validate(settings);profiles = {};sources = {};notes = []
        for kind, project_id in settings['events']['projects'].items():
            if project_id is None: continue
            path = self.events/event_id(project_id)/'project.json'
            before = sha(path);project = load(path)
            document = event_profiles.document(project.get('document'))
            if document['kind'] != kind:
                raise ValueError('事件工程类型与配方位置不匹配：'+kind)
            if sha(path) != before: raise ValueError('编译期间事件工程发生变化，请重试')
            profiles[kind] = document
            sources[kind] = dict(project=project_id, project_sha256=before,
                document_sha256=event_profiles.digest(document), name=project['name'],
                audition_controls=audition_controls(project['controls']))
            if document.get('physical_identity_confirmed') is not True:
                notes.append(project['name']+'：事件物理类型尚未确认')
            scope = normalize(document.get('source_job', {}).get('analysis_scope'))
            if scope['mode'] == 'band': notes.append(project['name']+'：仅为指定频带的候选')
        bridge = Bridge(self.workspace.repo)
        control = bridge.initial(0, bank)[0]
        control['dna']=settings['dna']
        control.update(mode=1, ignition=0, start_id=0, throttle=0., brake=0., gear=1, automatic=1,
                       backfire=1, legacy_event_gain=0., **settings['layers'])
        events = settings['events']
        control['events'].update(enabled=int(events['enabled']), manual_sequence=0,
            **{key: events[key] for key, *_ in MACROS})
        # An empty slot means silence even when the compiled reference event
        # bank contains a candidate of that type. Never inherit its timbre.
        control['events']['levels'] = [events['levels'][i] if kind in profiles else 0. for i, kind in enumerate(KINDS)]
        value = recipe.create(bridge, 0, control, '踏板驾驶', profiles,
            settings['startup'], settings['policy'], bank)
        recipe.validate(bridge, value)
        with Engine(bridge, 0, profiles, settings['startup'], settings['policy'], bank) as engine:
            engine.set(control)
        for source in sources.values():
            if sha(self.events/source['project']/'project.json') != source['project_sha256']:
                raise ValueError('编译期间事件来源发生变化，请重新保存')
        return value, dict(events=sources, notes=notes, bridge_sha256=bridge.sha256,
            source_effective_sha256=value['source_effective_sha256'],
            effective_event_levels=control['events']['levels'],
            event_controls='Only saved event document coefficients are adopted. Audition pitch/strength/decay/texture/hold/seed are preserved as provenance, not baked; common runtime event macros govern playback.',
            silence_policy='Unselected event kinds have zero levels, including compiled-bank candidates.')

    def changed(self, sources):
        result = []
        for source in sources.get('events', {}).values():
            path = self.events/source['project']/'project.json'
            if not path.is_file() or sha(path) != source['project_sha256']: result.append(source['project'])
        return sorted(set(result))
