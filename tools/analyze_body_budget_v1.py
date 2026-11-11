"""Check existing LF power before adding or repartitioning an oscillator layer."""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from drive_evidence_v1.sources import sha

args.out.mkdir(parents=True,exist_ok=False)
bands=[(28,120),(120,350),(350,1200)]
report=dict(schema='vsl.harmonic-body-budget/1',bands=bands,cases=[],
    limits=['Frozen short observation versus longer newly generated stationary statistics',
        'Same root and Welch window; no waveform/null or perceptual identity claim',
        'Existing full DNA already contains LF; independent physical sub-bass remains unidentified',
        'Six anchors from two contexts; not six engines or measured RPM/load coverage'])
for bank,baseline,subdir,normalized in [
    ('exterior_anchors_v1','exterior_anchors_v1','anchors_v2','normalized_float.wav'),
    ('cabin_anchors_v1','drive_evidence_v1','cabin_anchors_tapered','normalized_reference_float.wav')]:
    frozen=args.workspace/'baselines'/baseline
    manifest=frozen/'manifest.json'
    hashes={r['path']:r['sha256'] for r in json.loads(manifest.read_text(encoding='utf-8'))['files']}
    for item in json.loads((repo/'voices'/bank/'index.json').read_text(encoding='utf-8'))['voices']:
        prefix=f"evidence/{subdir}/{item['name']}/"
        def bound(name):
            path=frozen/(prefix+name)
            assert sha(path)==hashes[prefix+name]
            return path
        assert sha(bound('voice.model'))==item['model_sha256']
        reference,rate=sf.read(bound(normalized),always_2d=True)
        raw,other_rate=sf.read(bound('raw_1.0.wav'),always_2d=True)
        assert rate==other_rate==48000
        cycles=len(reference)/1024
        ratio=Fraction(46.875/item['base_hz']).limit_denominator(10000)
        reference=signal.resample_poly(reference,ratio.numerator,ratio.denominator,axis=0,window=('kaiser',8.6))
        stats=[]
        for requested in (8192,16384):
            size=min(requested,len(reference))
            def power(audio):
                hz,p=signal.welch(audio,rate,window='hann',nperseg=size,axis=0,detrend=False)
                return np.array([p[(hz>=lo)&(hz<hi)].sum(axis=0)*(hz[1]-hz[0]) for lo,hi in bands]).T
            a,b=power(reference),power(raw[24000:])
            stats.append(dict(window_samples=size,reference_power_LR=a.tolist(),dna_power_LR=b.tolist(),
                mean_power_change_db=(10*np.log10(b.mean(axis=0)/a.mean(axis=0))).tolist()))
        record=dict(name=item['name'],context=bank,base_hz=item['base_hz'],observed_cycles=cycles,
            source_manifest_sha256=sha(manifest),normalized_sha256=sha(bound(normalized)),
            model_sha256=sha(bound('voice.model')),raw_sha256=sha(bound('raw_1.0.wav')),measurements=stats)
        report['cases'].append(record)
        print(item['name'],[np.round(s['mean_power_change_db'],2).tolist() for s in stats],flush=True)
report['source_sha256']={Path(__file__).relative_to(repo).as_posix():sha(Path(__file__))}
(args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
