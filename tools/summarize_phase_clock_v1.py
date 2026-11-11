"""Preserve candidate failures and summarize the combined validation scope."""
import argparse,csv,json,shutil,sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',required=True,type=Path)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import sha
root=args.workspace/'references/analysis/phase_clock_v1'
def read(rel):return json.loads((root/rel).read_text(encoding='utf-8'))
original=read('attempt3/report.json');short=read('attempt2/report.json');held=read('controls_attempt6/report.json')
policy=read('policy_audit/report.json');chirp=read('chirplet_real/report.json');real=read('real_attempt2/report.json')
assert held['result']=='pass' and held['measured_cases']==16 and held['default_path_identical']
assert len(real['pairs'])==0 and policy['connected_reference5']==7
worst=float(max(max(abs(np.array(p['local_zero_shape_error_db']))) for p in original['pairs']))
assert worst>.5
saved=0
for report in sorted(root.rglob('report.json')):
    r=json.loads(report.read_text(encoding='utf-8'))
    for rel,digest in r.get('source_sha256',{}).items():
        dest=report.parent/'source'/rel;live=repo/rel
        if dest.exists():assert sha(dest)==digest,(str(report),rel)
        else:
            assert sha(live)==digest,(str(report),rel)
            dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(live,dest)
        saved+=1

fig,axes=plt.subplots(1,3,figsize=(15,4.5),layout='constrained')
x=np.arange(3)
for offset,key,label,source in [(-.25,'legacy_zero_shape_error_db','Legacy 4 cycles',original),
        (0,'local_zero_shape_error_db','2 cycles',short),(.25,'local_zero_shape_error_db','4 cycles + moment',original)]:
    values=[max(abs(np.array(p[key]))) for p in source['pairs']]
    axes[0].bar(x+offset,values,width=.24,label=label)
axes[0].axhline(.5,color='crimson',ls='--',lw=1)
axes[0].set(xticks=x,xticklabels=['Pair1','Pair2','Pair4'],ylabel='Max spurious colour dB',title='Original known sweeps')
axes[0].legend(fontsize=7)
values=[max(max(abs(np.array(c['shape_error_db']))) for c in row['cases']) for row in held['curves']]
axes[1].bar(range(4),values,color='#4b94b1');axes[1].axhline(.5,color='crimson',ls='--',lw=1)
axes[1].set(xticks=range(4),xticklabels=['Linear','Exp','Curve','Corner'],ylim=(0,.55),title='16 new known/noisy sweeps',ylabel='Max error vs accurate clock dB')
axes[2].bar(range(3),[7,4,7],color=['#6c8ebf','#d99062','#6c8ebf'])
axes[2].set(xticks=range(3),xticklabels=['FFT','Chirplet','Fallback'],ylim=(0,8.5),title='Real A: complete ref5 paths',ylabel='Passages out of8')
axes[2].text(.5,.02,'Ref10:0/8; no qualified rise/fall pair',transform=axes[2].transAxes,ha='center',fontsize=8)
fig.suptitle('Candidate controls do not establish real-recording calibration',fontsize=13)
fig.savefig(root/'comparison.png',dpi=140);plt.close(fig)

with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
for row in rows:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
previous=json.loads((repo/'research/state_colour_v2_summary.json').read_text(encoding='utf-8'))
for rel,digest in previous['unchanged_model_sha256'].items():assert sha(repo/rel)==digest,rel
for name,digest in previous['binary_sha256'].items():
    sub='Release' if name=='VslOscColour_checks.exe' else 'bin/Release'
    assert sha(repo/'handoff-build'/sub/name)==digest,name
notes=dict(schema='vsl.phase-clock-iterations/1',runtime_changed=False,combined_validation='not_passed',
    attempts=['attempt1:two-cycle joint projection reduces synthetic bias',
        'attempt2:replace equivalent projection with simple FFT; original worst0.216dB',
        'real_attempt1:global separate-carrier gate rejects all short-refined rise/fall pairs',
        'controls_attempt1:span roundoff triggers no-extrapolation guard; sources/failure retained',
        'controls_attempt2:NumPy integer serialization fails after computing results; sources/failure retained',
        'controls_attempt3/4:FFT coarse tracker disconnects sharp corners; noisy recording phase was wrongly compared to clean coefficients',
        'controls_attempt5:explicit noisy-reference comparison and chirplet tracker pass16new fixtures, but original hard fixture remains outside scope',
        'chirplet_real:only4/8paths versus FFT7/8; no blanket replacement',
        'controls_attempt6:FFT-first whole-path fallback passes16new fixtures',
        'policy_audit:all7old complete A paths unchanged; rise3 and all ref10paths remain absent',
        'attempt3:four-cycle moment correction still1.007dB on original pair4; not ready for model promotion',
        'real_attempt2/3:strict whole-passage independent agreement yields no qualified rising/falling pair'],
    interpretation='A failed global phase-constancy gate does not prove absent engine coherence: acoustic transfer phase may vary with pitch.')
(root/'iterations.json').write_text(json.dumps(notes,indent=2)+'\n',encoding='utf-8',newline='\n')
files=[p for p in (repo/'tools/phase_clock_v1').iterdir() if p.is_file()]
files += [repo/p for p in ('tools/state_dna_v1/compare.py','tools/explore_phase_clock_v1.py','tools/verify_phase_clock_v1.py',
    'tools/analyze_phase_clock_v1.py','tools/explore_chirp_clock_v1.py','tools/audit_phase_clock_policy_v1.py','tools/summarize_phase_clock_v1.py')]
report=dict(schema='vsl.phase-clock-summary/1',combined_validation='not_passed',runtime_changed=False,new_model_promoted=False,
    new_fixture_controls=dict(result='pass',cases=16,max_shape_db=held['maximum_phase_shape_error_db'],
        max_known_gain_error_db=held['maximum_known_shape_error_db'],max_stereo_phase_error_rad=held['maximum_stereo_phase_error_radians'],
        default_path_identical=True,negative_controls=held['negative_controls']),
    original_fixture_max_shape_error_db=worst,real_fft_paths=7,real_chirplet_paths=4,real_fallback_paths=7,
    real_qualified_rise_fall_pairs=0,c_index_entries_verified=len(rows),source_versions_verified=saved,
    evidence_root=str(root),source_sha256={p.relative_to(repo).as_posix():sha(p) for p in files},
    evidence_sha256={p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*')) if p.is_file()},
    unchanged_model_sha256=previous['unchanged_model_sha256'],unchanged_binary_sha256=previous['binary_sha256'],
    human_timbre_accepted=False,limits=['No full original+independent+real validation pass',
        'Global phase-coherence gate is conservative and confounded by pitch-dependent transfer',
        'No driver/load mapping, new audio model, runtime, device or speaker change'])
(repo/'research/phase_clock_v1_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(combined='not_passed',new_controls=16,original_max_db=worst,source_versions=saved,c_files=len(rows))))
