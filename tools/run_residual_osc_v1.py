"""Fit A/E additive residual profiles and render shared C oscillator clouds."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--probe',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from residual_osc_v1.sources import read,CASES
from residual_osc_v1.fit import fit,export
from residual_osc_v1.spectrum import matrices,error

repo=Path(__file__).resolve().parents[1]
args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.residual-osc-build/1',cases={},human_accepted=False,driving_attached=False,
    probe_sha256=sha(args.probe),seed=8121907,
    limits=['Mean spectra/coherence only; temporal envelope statistics not fitted',
        'Finite detuned OSC cloud is a procedural residual, not physical source separation',
        '1.2–8kHz fixed-anchor experiment; low rumble remains separate',
        'A/E camera contexts are fitted independently with the same algorithm; not different engines',
        'Only bounded0.9..1.1 pitch; no wide-RPM/state interpolation or real device guarantee'])
for name in CASES:
    out=args.out/name;out.mkdir()
    fixed,bases,provenance=read(args.workspace,repo,name)
    base=bases['1.0'][0]
    rows,evidence=fit(fixed,base[24000:])
    export(out/'voice.residual',rows)
    sf.write(out/'fixed_reference_float.wav',fixed,48000,subtype='FLOAT')
    record=dict(source=provenance,fit=evidence,rows=rows,profile_sha256=sha(out/'voice.residual'),renders=[])
    for pitch in (.9,1.,1.1):
        target=out/f'residual_{pitch:.1f}.wav'
        command=[str(args.probe),str(out/'voice.residual'),str(target),'8',str(pitch),'1',str(report['seed'])]
        subprocess.run(command,check=True,capture_output=True,timeout=90)
        residual,rate=sf.read(target,always_2d=True)
        assert rate==48000 and residual.shape==(384000,2) and np.isfinite(residual).all()
        assert not np.array_equal(residual[:192000],residual[192000:])
        base,path=bases[str(pitch)]
        mixed=base+residual
        sf.write(out/f'base_{pitch:.1f}.wav',base,48000,subtype='FLOAT')
        sf.write(out/f'mix_{pitch:.1f}.wav',mixed,48000,subtype='FLOAT')
        record['renders'].append(dict(pitch=pitch,command=command,base_source=str(path),base_sha256=sha(path),
            residual_sha256=sha(target),mixed_sha256=sha(out/f'mix_{pitch:.1f}.wav'),
            residual_peak=float(abs(residual).max()),mixed_peak=float(abs(mixed).max())))
        if pitch==1:
            desired=[dict(hz=r['hz'],power=r['power'],cross=[v*np.sqrt(np.prod(r['power'])) for v in r['coherence']]) for r in rows]
            record['residual_target_error']=error(desired,matrices(residual[24000:]))
            record['before_error']=error(matrices(fixed),matrices(base[24000:]))
            record['after_error']=error(matrices(fixed),matrices(mixed[24000:]))
    report['cases'][name]=record
    print(name,'residual/mix max',record['renders'][1]['residual_peak'],record['renders'][1]['mixed_peak'],flush=True)
report['source_sha256']={p.relative_to(repo).as_posix():sha(p) for p in
    [Path(__file__),*repo.joinpath('tools/residual_osc_v1').glob('*.py'),*repo.joinpath('modules/sound_residual').glob('*.[ch]'),
     *repo.joinpath('experiments/residual_osc_v1').glob('*.c')]}
(args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
