"""Compile all six existing acoustic anchors into a context-separated residual atlas."""
import argparse
import json
from pathlib import Path
from fractions import Fraction
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
parser.add_argument('--models-out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from drive_evidence_v1.sources import sha
from residual_osc_v1.fit import fit,export
from residual_osc_v1.spectrum import BANDS

args.out.mkdir(parents=True,exist_ok=False)
args.models_out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.residual-atlas-fit/1',human_accepted=False,cases=[],limits=[
    'Two recording contexts of one V10 family; not six real engines',
    'Only mean spectral matrices; no measured load/state or temporal envelopes',
    'Fixed-Hz inharmonic cloud; root interpolates covariance, not carrier frequency',
    'Whole bands above a conservative observation budget are zero, not extrapolated',
    'A root/RPM remains engineering; E evidence does not transfer to A'])
for bank_name,baseline,subdir,normalized in [
    ('exterior_anchors_v1','exterior_anchors_v1','anchors_v2','normalized_float.wav'),
    ('cabin_anchors_v1','drive_evidence_v1','cabin_anchors_tapered','normalized_reference_float.wav')]:
    bank=repo/'voices'/bank_name
    records=json.loads((bank/'index.json').read_text(encoding='utf-8'))['voices']
    frozen=args.workspace/'baselines'/baseline
    manifest=json.loads((frozen/'manifest.json').read_text(encoding='utf-8'))
    hashes={r['path']:r['sha256'] for r in manifest['files']}
    for item in records:
        name=item['name'];prefix=f'evidence/{subdir}/{name}/'
        def bound(filename):
            key=prefix+filename;path=frozen/key
            assert sha(path)==hashes[key],key
            return path
        assert sha(bound('voice.model'))==sha(bank/item['file'])==item['model_sha256']
        build=json.loads(bound('build.json').read_text(encoding='utf-8'))
        if bank_name=='exterior_anchors_v1':
            warp=build['phase_polish'];cutoff=warp['source_cutoff_hz'];maximum=warp['inferred_root_hz_range'][1]
        else:
            warp=build['warp'];cutoff=14000.;maximum=warp['root_hz_range'][1]
        root=item['base_hz'];usable=(cutoff-600)*root/maximum
        source,rate=sf.read(bound(normalized),always_2d=True)
        assert rate==48000 and source.shape[1]==2 and np.isfinite(source).all()
        ratio=Fraction(46.875/root).limit_denominator(10000)
        fixed=signal.resample_poly(source,ratio.numerator,ratio.denominator,axis=0,window=('kaiser',8.6))
        base,rate=sf.read(bound('raw_1.0.wav'),always_2d=True)
        assert rate==48000 and base.shape==(384000,2)
        rows,evidence=fit(fixed,base[24000:])
        active=[]
        for row in rows:
            supported=row['hz'][1]<=usable;active.append(supported)
            if not supported:row['power']=[0.,0.];row['coherence']=[0.,0.]
        output=args.out/name;output.mkdir()
        export(output/'voice.residual',rows)
        export(args.models_out/(name+'.residual'),rows)
        sf.write(output/'reference.wav',fixed,48000,subtype='FLOAT')
        record=dict(name=name,context=bank_name,base_hz=root,model_sha256=item['model_sha256'],
            file=name+'.residual',profile_sha256=sha(output/'voice.residual'),
            source_manifest_sha256=sha(frozen/'manifest.json'),normalized_sha256=sha(bound(normalized)),
            base_render_sha256=sha(bound('raw_1.0.wav')),source_build_sha256=sha(bound('build.json')),
            conservative_usable_top_hz=usable,active_bands=active,rows=rows,fit=evidence,
            budget_method='(source FIR cutoff -600Hz) * anchor root / max observed root; engineering margin')
        report['cases'].append(record)
        print(name,'active bands',sum(active),'usable',round(usable),flush=True)
report['source_sha256']={p.relative_to(repo).as_posix():sha(p) for p in
    [Path(__file__),repo/'tools/residual_osc_v1/fit.py',repo/'tools/residual_osc_v1/spectrum.py']}
(args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
index=dict(schema='vsl.residual-atlas-models/1',fit_report_sha256=sha(args.out/'report.json'),
    voices=[{k:r[k] for k in ('name','context','base_hz','model_sha256','file','profile_sha256',
                            'conservative_usable_top_hz','active_bands')} for r in report['cases']],
    human_accepted=False,limits=report['limits'])
(args.models_out/'index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
