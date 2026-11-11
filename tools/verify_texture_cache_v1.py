"""Verify texture-cache optimization against immutable C audio and paired timing."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
repository=Path(__file__).resolve().parents[1]
args.out.mkdir(parents=True,exist_ok=False)

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

frozen=args.workspace/'baselines/exterior_anchors_v1'
manifest=json.loads((frozen/'manifest.json').read_text(encoding='utf-8'))
bound={row['path']:row['sha256'] for row in manifest['files']}
def frozen_file(relative):
    path=frozen/relative
    assert sha(path)==bound[relative]
    return path

probe=repository/'handoff-build/bin/Release/VslSoundDna_probe.exe'
report=dict(schema='vsl.texture-cache/1',result='pending',parity=[],timing=[],
    source_sha256=sha(repository/'modules/sound_dna/texture.c'),binary_sha256=sha(probe),
    frozen_commit=manifest['source_commit'],limits='Same MSVC build/runtime; paired offline timing, not device validation')
bank=json.loads((repository/'voices/exterior_anchors_v1/index.json').read_text(encoding='utf-8'))
for row in bank['voices']:
    model=repository/'voices/exterior_anchors_v1'/row['file']
    assert sha(model)==row['model_sha256']
    for pitch in (.9,1.,1.1):
        target=args.out/f"{row['name']}_{pitch:.1f}.wav"
        subprocess.run([str(probe),str(model),str(target),'8',str(pitch),'1','1'],check=True,capture_output=True,timeout=90)
        gold=frozen_file(f"evidence/anchors_v2/{row['name']}/raw_{pitch:.1f}.wav")
        assert sha(target)==sha(gold)
        report['parity'].append(dict(name=row['name'],pitch=pitch,whole_wav_equal=True,sha256=sha(target)))

# Include the accepted fixed-context DNA and LF, independent of the new atlas.
for name,model in [('accepted_dna',repository/'voices/dna_bank_v1/V10 Exterior.model'),
                   ('accepted_lf',repository/'voices/coherent_low_v1/measured_phase.model')]:
    old=args.out/(name+'_before.wav');new=args.out/(name+'_after.wav')
    for exe,out in [(frozen_file('bin/VslSoundDna_probe.exe'),old),(probe,new)]:
        subprocess.run([str(exe),str(model),str(out),'4','1','1','1'],check=True,capture_output=True,timeout=60)
    assert sha(old)==sha(new)
    report['parity'].append(dict(name=name,whole_wav_equal=True,sha256=sha(new)))

models=[repository/'voices/exterior_anchors_v1'/row['file'] for row in bank['voices']]
old_exe=frozen_file('bin/VslAtlasDrive_probe.exe')
new_exe=repository/'handoff-build/bin/Release/VslAtlasDrive_probe.exe'
for name,exe in [('before0',old_exe),('after0',new_exe),('after1',new_exe),('before1',old_exe)]:
    prefix=args.out/name
    command=[str(exe),str(models[0]),str(models[1]),str(prefix)]
    for model in models[2:]:command+=['--anchor',str(model)]
    command+=['--seconds','12','--scenario','auto','--root-per-rpm',str(1/120)]
    result=subprocess.run(command,check=True,capture_output=True,timeout=90)
    measured=json.loads((args.out/(name+'_report.json')).read_text(encoding='utf-8'))
    wav=args.out/(name+'_render.wav')
    report['timing'].append(dict(name=name,process_seconds=measured['process_seconds'],
        max_block_seconds=measured['max_block_seconds'],overruns=measured['block_budget_exceedances'],
        command=command,binary_sha256=sha(exe),output_sha256=sha(wav)))
assert len({r['output_sha256'] for r in report['timing']})==1
before=np.mean([r['process_seconds'] for r in report['timing'] if r['name'].startswith('before')])
after=np.mean([r['process_seconds'] for r in report['timing'] if r['name'].startswith('after')])
report.update(result='pass',paired_mean_before_seconds=float(before),paired_mean_after_seconds=float(after),
    processing_speedup=float(before/after),verifier_sha256=sha(__file__))
(args.out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(result='pass',parity_runs=len(report['parity']),speedup=report['processing_speedup'],
    before_seconds=float(before),after_seconds=float(after))))
