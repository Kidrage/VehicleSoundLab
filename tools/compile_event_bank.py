"""Compile selected material-informed profiles into a complete, explicit C bank."""
import argparse
import hashlib
import json
from pathlib import Path
from event_authoring.export import compile_bank
from event_authoring.model import KINDS


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',type=Path,action='append',default=[]);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();profiles={}
    for path in args.profile:
        document=json.loads(path.read_text(encoding='utf-8-sig'));kind=document['kind']
        if kind not in KINDS or kind in profiles:raise ValueError('Unknown or duplicated event kind')
        profiles[kind]=document|dict(profile_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    empty=dict(gated=0,duration_seconds=.1,attack_seconds=.001,release_seconds=.01,sweep_seconds=0,level=0,modes=[],bands=[])
    for kind in KINDS:
        if kind not in profiles:profiles[kind]=dict(kind=kind,status='unavailable; no compiled material profile',parameters=dict(empty))
    bank=dict(schema='vsl.event-bank/1',profiles=profiles,
        available_mask=sum(1<<i for i,key in enumerate(KINDS) if profiles[key]['parameters']['modes'] or profiles[key]['parameters']['bands']),
        note='Availability proves only a compiled candidate, never timbre acceptance or physical identity.')
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'profiles.json').write_text(json.dumps(bank,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    compile_bank(bank,args.output/'profiles.h')
    print(json.dumps(dict(available_mask=bank['available_mask'],output=str(args.output))))


if __name__=='__main__':main()
