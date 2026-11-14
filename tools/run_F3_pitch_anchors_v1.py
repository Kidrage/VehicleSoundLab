"""Five predeclared F3 local observations through unchanged extraction gates."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from research_archive_v1 import load, save, sha

p=argparse.ArgumentParser(description=__doc__)
for key in ('workspace','out'):
    p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[key]='2'
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from local_voice_batch_v1.batch import controls,fit_case
from local_voice_batch_v1.render import RAW_PROTOCOL,BANDLIMITED_PROTOCOL,playback_argument
from local_voice_batch_v1.bandlimited_controls import run as bandlimited_controls

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},inputs={},cases=[])
try:
    names=['tools/run_F3_pitch_anchors_v1.py','research/F3_pitch_anchors_v1_plan.json',
        'research/F3_display_rpm_v1_annotations.json','tools/research_archive_v1.py',
        'tools/drive_evidence_v1/sources.py','tools/drive_evidence_v1/family.py',
        'tools/shift_evidence_v1/spectrum.py','tools/B_shift_voice_v1/selection.py',
        'tools/decel_source_v1/aperture.py','tools/decel_source_v1/checks.py','tools/exterior_clock_v1/warp.py',
        'tools/local_voice_batch_v1/batch.py','tools/local_voice_batch_v1/render.py',
        'tools/local_voice_batch_v1/audit_kernels.py','tools/local_voice_batch_v1/bandlimited_controls.py',
        'tools/sustain_osc_v1/oracle.py']
    names += [v.relative_to(repo).as_posix() for v in (repo/'tools/sound_dna').glob('*.py')]
    for n in sorted(set(names)):
        dest=a.out/'exact_sources'/n;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/n,dest);r['sources'][n]=sha(repo/n)
    plan=load(repo/'research/F3_pitch_anchors_v1_plan.json')
    probe=repo/'build-bandlimited-dna-v1/bin/Release/sound_dna_bandlimited_export.exe'
    assert subprocess.check_output([str(probe),'--describe'],cwd=repo).decode().strip()==BANDLIMITED_PROTOCOL
    assert playback_argument(RAW_PROTOCOL,90)==1 and playback_argument(BANDLIMITED_PROTOCOL,90)==90
    try:playback_argument('unknown',90)
    except ValueError:pass
    else:raise AssertionError('Unknown export protocol accepted')
    r['export_protocol']=BANDLIMITED_PROTOCOL
    r['known_before_source']=controls(plan)
    r['known_bandlimited_before_source']=bandlimited_controls(a.out/'known_bandlimited',probe,repo)
    save(a.out/'report.json',r)
    catalog=a.workspace/'references/segments_v1.json'
    assert sha(catalog)==sha(repo/'references/segments_v1.json')
    r['inputs'][str(catalog)]=sha(catalog)
    for key in ('raw','master'):
        source=load(catalog)['sources']['F3'];path=a.workspace/source[key]
        assert sha(path)==source[key+'_sha256'];r['inputs'][str(path)]=sha(path)
    r['inputs'][str(probe)]=sha(probe)
    for case in plan['cases']:
        row=fit_case(a.workspace,case,plan,a.out/case['name'],probe,repo)
        r['cases'].append(row);save(a.out/case['name']/'result.json',row);save(a.out/'report.json',r)
        print(dict(name=case['name'],qualified=row['qualified'],stage=row['stage'],
                   root_hz=row.get('extraction',{}).get('root_hz'),heldout=row.get('extraction',{}).get('heldout_coherence')),flush=True)
    r.update(result='fixed_F3_pitch_anchors_checked',qualified=sum(v['qualified'] for v in r['cases']),
        excluded=sum(not v['qualified'] for v in r['cases']),runtime_changed=False,new_timbre_accepted=False,
        physical_RPM_or_load=False,generic_phase_qualified=False,room=False,PCM_timeline=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
