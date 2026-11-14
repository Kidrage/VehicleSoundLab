"""Archive all new idle evidence, with scalar diagnostic arithmetic checks."""
import argparse,csv,cmath,math,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha,freeze,verify,append_index
root=a.workspace/'baselines/idle_cyclic_detail_v1'
if a.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/idle_cyclic_detail_v1'
observed=load(evidence/'observe1/report.json');audit=load(evidence/'audit1/report.json');plot=load(evidence/'plot1/report.json')
assert observed['result']=='idle_signed_lag_structure_observed' and len(observed['observations'])==32
assert audit['result']=='passed' and len(audit['observations'])==32 and plot['result']=='published'
assert audit['input_report_sha256']==plot['input_report_sha256']==sha(evidence/'observe1/report.json')
assert plot['audit_sha256']==sha(evidence/'audit1/report.json')
sources=set(observed['sources'])
for name,digest in observed['sources'].items():assert sha(repo/name)==digest==sha(evidence/'observe1/exact_sources'/name)
curves={}
for row in observed['observations']:
    path=evidence/'observe1'/row['file'];assert sha(path)==row['sha256']
    with np.load(path) as f:curves[row['label']]=f['covariance']
for name,part,filename in [('tools/audit_idle_cyclic_detail_v1.py','audit1','executed_auditor.py'),
    ('tools/plot_idle_cyclic_detail_v1.py','plot1','executed_plot.py'),
    ('research/idle_cyclic_detail_v1_diagnostic.json','plot1','diagnostic_plan.json')]:
    assert sha(repo/name)==sha(evidence/part/filename);sources.add(name)
with np.load(evidence/'plot1/zero_match_diagnostic.npz') as f:
    factor=f['factor'];corrected=f['corrected_mean'];source=f['source'];mean=f['generated_mean']
generated=[curves[x['label']] for x in observed['observations'] if x['group']=='relation_full']
max_mean=max_factor=max_corrected=0.
for lag in range(193):
    for b in range(4):
        for k in range(6):
            values=[complex(c[lag,b,k]) for c in generated]
            independent=complex(math.fsum(v.real for v in values)/12,math.fsum(v.imag for v in values)/12)
            max_mean=max(max_mean,abs(independent-mean[lag,b,k]))
            ratio=complex(source[0,96,b,k])/complex(mean[96,b,k])
            max_factor=max(max_factor,abs(ratio-factor[b,k]))
            max_corrected=max(max_corrected,abs(independent*ratio-corrected[lag,b,k]))
assert max_mean<1e-14 and max_factor<1e-14 and max_corrected<1e-14
for part,i in [('train',0),('check',1)]:
    for b in range(4):
        v=math.sqrt(math.fsum(abs(complex(corrected[l,b,k])-complex(source[i,l,b,k]))**2
            for l in range(193) for k in range(6))/(193*6))
        assert abs(v-plot['zero_match_diagnostic']['parts'][part][str(b)]['complex_rms'])<1e-14
scalar=dict(result='passed',all193x4x6_mean_factor_and_corrected=True,all8_RMS=True,
    mean_error=max_mean,factor_error=max_factor,corrected_error=max_corrected,
    diagnostic_not_audio_or_positive_covariance_model=True)
save(evidence/'scalar_diagnostic_audit.json',scalar)
for row in plot['figures']:
    path=evidence/'plot1'/row['file'];assert sha(path)==row['sha256']
    name='research/idle_cyclic_detail_v1_'+row['file'];shutil.copy2(path,repo/name);sources.add(name)
old=load(a.workspace/'baselines/idle_microtexture_c_v1/inputs/C_files_sha256.json')
voices=load(a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json')
assert len(old)==612 and len(voices)==67
assert all(sha(repo/k)==v for k,v in {**old,**voices}.items())
rows=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
assert len(rows)==620 and all(sha(repo/row[0])==row[4] for row in rows[1:])
parents=['idle_conditioned_detail_v1','idle_phase_recipe_v1','fixed_source_profiles_v1']
inputs={name+'_manifest.json':a.workspace/'baselines'/name/'manifest.json' for name in parents}
tables={name:{x['path']:x['sha256'] for x in load(path)['files']} for name,path in zip(parents,inputs.values())}
for name,digest in observed['inputs'].items():
    path=Path(name);assert sha(path)==digest
    relative=path.relative_to(a.workspace/'baselines');parent=relative.parts[0]
    assert parent in tables and tables[parent][Path(*relative.parts[1:]).as_posix()]==digest
sources.update(['tools/package_idle_cyclic_detail_v1.py','research/怠速短时声纹关联V1.md',
    'AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
inputs['data_workspace_AGENTS']=a.workspace/'AGENTS.md'
validation=dict(schema='vsl.idle-cyclic-detail-freeze/1',result='source_structure_evidence_not_new_audio',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    observations=32,all193signed_source_lags_direct=True,all32cases7signed_lags_direct=True,
    all32inputs_independent_filter_and_phase_regeneration=True,scalar_diagnostic_audit=scalar,
    magnitude_curve_distances=plot['magnitude_curve_distances'],
    zero_lag_matched_diagnostic=plot['zero_match_diagnostic'],
    complete3figures_viewed=True,existing619C_H_and67voices_exact=True,new_audio_generated=False,
    runtime_changed=False,pending_idle_recipe_changed=False,listening_accepted=False,
    next='Judge existing phase candidate; remaining signed-lag gap motivates a small source-derived phase-conditioned resonant-shape study with positive factor parameterization. No extra HF cloud or blind AM gain. Finite listening is useful without exact all-moment matching; no unheard C/default promotion. Original phase qualifications and full goal remain active.')
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/idle_cyclic_detail_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['idle_cyclic_detail_v1','baselines/idle_cyclic_detail_v1/manifest.json',result['file_count'],
    result['manifest_sha256'],'32cases/all193source/7allcase direct/filter+phase;allcurves/zero-match scalar',
    'Evidence/notnewaudio;posthoczeromatchnotpositivegenerator;619C-H67voicesunchanged',
    'research/怠速短时声纹关联V1.md | research/idle_cyclic_detail_v1_summary.json','baselines/idle_cyclic_detail_v1/validation.json'])
print(result)
