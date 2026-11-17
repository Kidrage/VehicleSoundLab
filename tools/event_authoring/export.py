"""Compile editable JSON into C-only parameter structs."""
import json
import hashlib
from pathlib import Path
from .model import KINDS,validate


def number(v):return format(float(v),'.17g')


def c_profile(p):
    validate(p)
    modes=','.join('{'+','.join(number(m.get(k,0)) for k in ('hz','amplitude','phase','decay_seconds','end_hz','attack_seconds'))+'}' for m in p['modes']) or '{0}'
    bands=','.join('{'+','.join(number(b[k]) for k in ('hz','q','amplitude','attack_seconds','decay_seconds'))+'}' for b in p['bands']) or '{0}'
    scalar=','.join(number(p[k]) for k in ('duration_seconds','attack_seconds','release_seconds','sweep_seconds','level'))
    extra=','+number(p['noise_lowpass_hz']) if 'noise_lowpass_hz' in p else ''
    if 'contours' in p:
        extra=','+number(p.get('noise_lowpass_hz',0))+',{' + (','.join(
            '{'+str(len(c['seconds']))+','+number(c['low_hz'])+','+number(c['high_hz'])+
            ',{'+','.join(map(number,c['seconds']))+'},{'+','.join(map(number,c['gain']))+'}}'
            for c in p['contours']) or '{0}')+'}'
    return '{'+f"{len(p['modes'])},{len(p['bands'])},{int(p['gated'])},"+scalar+',{'+modes+'},{'+bands+'}'+extra+'}'


def compile_bank(document,path):
    if document['schema']!='vsl.event-bank/1' or set(document['profiles'])!=set(KINDS):raise ValueError('Incomplete event bank')
    text='/* Generated parameters; provenance is in the adjacent JSON. No PCM data. */\n'
    identity=hashlib.sha256(json.dumps(document,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')).hexdigest()
    text+='#define VSL_EVENT_BANK_SHA256 "'+identity+'"\n'
    text+='#include "event_synth/api.h"\nstatic const EsProfile vsl_event_profiles[ES_TYPES]={\n'
    text+=',\n'.join('  /* '+key+' */ '+c_profile(document['profiles'][key]['parameters']) for key in KINDS)+'\n};\n'
    Path(path).write_text(text,encoding='utf-8')
