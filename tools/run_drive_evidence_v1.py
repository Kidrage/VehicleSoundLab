"""Observe approved contexts before assigning engine-state / acoustic anchors."""
import argparse
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--ffmpeg', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.workspace / 'tools/python_deps'))
from drive_evidence_v1.sources import read, sha
from drive_evidence_v1.audio import observe as audio_observe
from drive_evidence_v1.video import observe as video_observe

args.out.mkdir(parents=True, exist_ok=False)
cases = [('A_exterior_low_rev', 'order_candidates'),
         ('A_exterior_blips', 'exterior_dynamic_observation'),
         ('A_exterior_moving', 'exterior_dynamic_observation'),
         ('B_cabin_pull', 'interior_channel_observation'),
         ('D_dyno_gears_context', 'audio_transition_observation'),
         ('E_corsa_second_context', 'cabin_dynamic_observation')]
report = dict(schema='vsl.drive-evidence-observation/1', cases={}, manual_annotation_completed=False)
for identity, use in cases:
    out = args.out / identity
    out.mkdir()
    audio, provenance = read(args.workspace, identity, use)
    report['cases'][identity] = dict(provenance=provenance, audio=audio_observe(audio, provenance, out))
    print(identity, 'audio observed', flush=True)
out = args.out / 'E_video'
out.mkdir()
report['video'] = video_observe(args.workspace, out, args.ffmpeg)
report['tools_sha256'] = {str(p.relative_to(Path(__file__).parent)).replace('\\', '/'): sha(p)
    for p in [Path(__file__), *Path(__file__).with_name('drive_evidence_v1').glob('*.py')]}
(args.out / 'observations.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(dict(output=str(args.out), video_frames=len(report['video']['frames']))))
