"""Audit failed original prerequisite and the declared residual-screen false negative."""
import argparse
import shutil
import sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha
from native_chirp_audit_v1.wave import near
from native_chirp_audit_v1.temporal import audit_temporal
from chirp_motion_controls_v1.audit_inputs import inventory,initialization
from native_phase_patch_v1.audit_wave import check as check_wave
from native_phase_patch_v1.audit_link import check as check_link
from candidate_presence_v1.audit_presence import proposal,presence
from candidate_presence_v1.audit_scores import check as check_scores
from candidate_presence_v1.audit_fixture import check as check_fixture
from candidate_residual_v1.audit_screen import check as check_screen

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',windows=0,native_lines=0,raw_lines=0,screen_tests=0,postfit_tests=0,
    maximum_waveform_error=0.,maximum_support_error=0.,maximum_normal_error=0.,maximum_optimality_error=0.,
    maximum_peak_error=0.,maximum_screen_cost_error=0.,maximum_screen_gain_error=0.,
    maximum_screen_coefficient_error=0.,maximum_postfit_cost_error=0.,maximum_postfit_gain_error=0.,prerequisite_failures=[])
names=['tools/audit_candidate_residual_v1.py','tools/candidate_residual_v1/audit_screen.py',
    'tools/native_chirp_audit_v1/wave.py','tools/native_chirp_audit_v1/temporal.py',
    'tools/chirp_motion_controls_v1/audit_inputs.py','tools/research_archive_v1.py']
names += [v.relative_to(repo).as_posix() for directory in ['candidate_presence_v1','native_phase_patch_v1']
          for v in (repo/'tools'/directory).glob('audit*.py')]
for name in names:
    dest=a.out/'exact_sources'/name
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(repo/name,dest)
try:
    report=load(a.input/'report.json')
    assert report['result']=='failed' and report['error']=="AssertionError('Original exact-cubic prerequisite failed')"
    assert report['executed_windows']==12 and report['prerequisite_passed'] is False and report['real_source_read'] is False
    assert [v['case'] for v in report['summaries']]==['cubic_control']
    assert sorted(v.name for v in a.input.iterdir() if v.is_dir())==['cubic_control','exact_sources']
    for name,h in report['sources'].items():assert sha(repo/name)==h==sha(a.input/'exact_sources'/name)
    baseline=a.workspace/'baselines/candidate_presence_v1'
    assert sha(baseline/'manifest.json')==report['parent_manifest_sha256']
    table={v['path']:v['sha256'] for v in load(baseline/'manifest.json')['files']}
    for name,h in report['parent_files'].items():assert sha(baseline/name)==h==table[name]
    source=baseline/'evidence/observe1/cubic_control'
    folder=a.input/'cubic_control'
    audio=np.load(folder/'signal.npz')['audio']
    near(audio,np.load(source/'signal.npz')['audio'],0)
    truth=load(folder/'truth.json')
    assert truth==load(source/'truth.json')
    p0=load(a.workspace/'baselines/chirp_motion_controls_v1/evidence/observe1/report.json')['plan']
    r['maximum_signal_error']=check_fixture('cubic_control',p0,audio,truth['rows'])
    obs=load(folder/'initialization.json')
    assert obs==load(source/'initialization.json')
    native=load(folder/'native_fits.json')
    assert native==load(source/'native_fits.json')
    raw=load(folder/'raw_fits.json')
    rows=load(folder/'fits.json')
    candidates=load(folder/'candidate_proposals.json')
    proposals=load(folder/'proposals.json')
    screens=load(folder/'screens.json')
    tests=load(folder/'presence.json')
    assert len(native)==len(raw)==len(rows)==len(candidates)==len(proposals)==len(screens)==len(tests)==12
    fp=load(repo/'research/accel_chirp_v1_plan.json')
    rp=load(repo/'research/accel_ridges_v1_plan.json')
    lp=load(repo/'research/low_chirp_v1_plan.json')
    initialization(obs['inventories'],obs['ratios'],obs['initial'])
    for i in range(12):
        previous=rows[i-1] if i else None
        nz=np.load(source/f'native_{i:02d}.npz')
        z=np.load(folder/f'tile_{i:02d}.npz')
        sz=np.load(folder/f'screen_{i:02d}.npz')
        near(nz['audio'],audio[i*12000:(i+1)*12000],0)
        near(z['audio'],nz['audio'],0)
        scanned=inventory(nz['audio'],obs['inventories'][i],rp)
        r['maximum_peak_error']=max(r['maximum_peak_error'],scanned['error'])
        assert scanned['strongest_index']==obs['guides'][i]['native_inventory_index']
        near(scanned['strongest_hz'],obs['guides'][i]['observed_hz'],1e-8)
        near(obs['ratios'][i],obs['guides'][i]['observed_hz']/obs['guides'][0]['observed_hz'])
        proposal(obs['inventories'][i],obs['initial'][i],previous,candidates[i])
        checked=check_screen(native[i],nz,nz['audio'],candidates[i],previous,screens[i],sz,proposals[i],fp)
        r['screen_tests']+=checked['tests']
        for key in ['cost_error','gain_error','coefficient_error']:r['maximum_screen_'+key]=max(r['maximum_screen_'+key],checked[key])
        for row,array,inv,init in [(native[i],nz,obs['inventories'][i],obs['initial'][i]['initial_chirp']),
                                  (raw[i],z,proposals[i]['inventory'],proposals[i]['initial_chirp'])]:
            m=len(row['lines'])
            near(array['nominal'],np.array(inv['bin'])*4)
            near(array['initial'][:m],np.zeros(m))
            for part in [array['initial'][m:2*m],array['initial'][2*m:]]:near(part,np.clip(init,-500+1e-6,500-1e-6))
            value=check_wave(array,row,fp)
            for key in ['waveform_error','support_error','normal_error','optimality_error']:r['maximum_'+key]=max(r['maximum_'+key],value[key])
        if not proposals[i]['added_bins']:
            assert raw[i]==native[i] and set(z.files)==set(nz.files)
            for key in z.files:near(z[key],nz[key],0)
        value=presence(z,raw[i],rows[i],proposals[i],previous,tests[i])
        r['postfit_tests']+=value['tests']
        r['maximum_postfit_cost_error']=max(r['maximum_postfit_cost_error'],value['maximum_cost_error'])
        r['maximum_postfit_gain_error']=max(r['maximum_postfit_gain_error'],value['maximum_gain_error'])
        r['windows']+=1
        r['native_lines']+=len(native[i]['lines'])
        r['raw_lines']+=len(raw[i]['lines'])
        reasons=[]
        if not rows[i]['success']:reasons.append('optimizer_failure')
        if len(rows[i]['lines'])!=10:reasons.append('mode_count')
        if not all(v['eligible'] for v in rows[i]['lines']):reasons.append('line_eligibility')
        if len(rows[i]['lines'])==10:
            for name,key,limit in [('frequency','frequency_hz',.06),('rate','chirp_hz_per_second',.15),('curvature','curvature_hz_per_second2',1.2)]:
                if max(abs(v[key]-u[key]) for v,u in zip(rows[i]['lines'],truth['rows'][i]['lines']))>=limit:reasons.append(name)
        relative=float(np.linalg.norm(z['residual'])/np.linalg.norm(z['audio']))
        if relative>=1e-5:reasons.append('waveform_relative_error')
        if reasons:r['prerequisite_failures'].append(dict(window=i,reasons=reasons,relative_residual=relative))
    links=load(folder/'links.json')
    assert set(links)=={'native_old','native_boundary','unscreened_old','unscreened_boundary','screened_old','screened_boundary'}
    for key,linked in links.items():
        value=native if key.startswith('native') else rows if key.startswith('screened') else load(source/'fits.json')
        if key.endswith('_old'):audit_temporal(value,linked,lp)
        else:check_link(value,linked)
    check_link(truth['rows'],truth['boundary'])
    scores=load(folder/'scores.json')
    for key in links:check_scores(links[key],truth['rows'],scores[key])
    item=dict(case='cubic_control',windows=12,successful=sum(v['success'] for v in rows),
        local_lines=sum(len(v['lines']) for v in rows),eligible_lines=sum(v['eligible'] for row in rows for v in row['lines']),
        failed_windows=[i for i,v in enumerate(rows) if not v['success']],
        variants={key:{k:v[k] for k in ['longest_track','tracks_atleast5','components','mixed_identity_tracks','unexplained_absent_query_hits']} for key,v in scores.items()})
    assert report['summaries']==[item]
    prerequisite=load(a.input/'prerequisite.json')
    assert prerequisite['failures']==r['prerequisite_failures']
    tracks=links['screened_boundary']['tracks']
    assert prerequisite['ten_complete_tracks']==(len(tracks)==10 and all(len(v['windows'])==12 for v in tracks))
    assert prerequisite['passed'] is False and [v['window'] for v in r['prerequisite_failures']]==[11]
    assert r['prerequisite_failures'][0]['reasons']==['mode_count','waveform_relative_error']
    r['screen_gains']=[dict(window=i,gain_LR=v['tests'][0]['partial_gain_LR'],passed=v['tests'][0]['passed']) for i,v in enumerate(screens) if v['tests']]
    for filename,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
        values=load(a.workspace/'baselines/idle_microtexture_c_v1/inputs'/filename)
        assert len(values)==count
        for name,h in values.items():assert sha(repo/name)==h
    r.update(result='all12_prerequisite_screen_false_negative_inputs_raw_accepted_nulls_graphs_scores_verified',
        input_report_sha256=sha(a.input/'report.json'),remaining96_executed=False,
        qualified=False,C_H_unchanged=612,old_voices_unchanged=67,real_source_read=False)
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    raise
finally:save(a.out/'report.json',r)
print({key:r[key] for key in ['result','windows','native_lines','raw_lines','screen_tests','postfit_tests','prerequisite_failures','screen_gains']})
