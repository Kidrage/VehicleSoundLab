"""An editable parameter preset; all audio and triggering stay in existing C."""
from copy import deepcopy
import json
from .event_profiles import document
from event_authoring.material_reviews import ensure_live_reference


def profile(repo,extended=False):
    name='reference_afterfire_G_v2.json' if extended else 'procedural_afterfire_v1.json'
    value=document(json.loads((repo/'presets/events'/name).read_text(encoding='utf-8')))
    ensure_live_reference({'afterfire':value})
    return value


def defaults(bridge,selection,control,features,bank=None):
    """Only the current default V10 opts in; other timbres/frozen apps don't."""
    value=deepcopy(control)
    if selection!=0 or bank is not None or not features&128 or not features&256:
        return value,{},deepcopy(bridge.event_policy_defaults)
    value['events'].update(enabled=1,gain=.70,pitch=1.,decay=1.,texture=1.,manual_sequence=0)
    value['events']['levels']=[0.,0.,0.,.80,0.,0.,0.]
    policy=deepcopy(bridge.event_policy_defaults)
    policy.update(afterfire_min_count=1,afterfire_max_count=2,afterfire_probability=1.,afterfire_cooldown_seconds=.35)
    extended=bool(features&1024)
    if extended:
        policy.update(afterfire_min_count=6,afterfire_max_count=10,afterfire_delay_seconds=.024,
            afterfire_interval_min_seconds=.040,afterfire_interval_max_seconds=.110,
            afterfire_repeat_gain=.97,afterfire_cooldown_seconds=.65)
    return value,{'afterfire':profile(bridge.repo,extended)},policy
