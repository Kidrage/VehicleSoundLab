"""Independent all-window proposal, conditional presence, wave and score audit."""
import argparse
import math
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
from chirp_motion_controls_v1.audit_inputs import signal,truth_rows,inventory,initialization
from native_phase_patch_v1.audit_wave import check as check_wave
from native_phase_patch_v1.audit_link import check as check_link
from candidate_presence_v1.audit_presence import proposal,presence
from candidate_presence_v1.audit_scores import check as check_scores
from candidate_presence_v1.audit_fixture import check as check_fixture

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',windows=0,native_lines=0,raw_lines=0,conditional_tests=0,
    maximum_signal_error=0.,maximum_waveform_error=0.,maximum_support_error=0.,
    maximum_normal_error=0.,maximum_optimality_error=0.,maximum_peak_error=0.,
    maximum_null_cost_error=0.,maximum_partial_gain_error=0.,cases=[],prerequisite_failures=[])
for name in ['tools/audit_candidate_presence_v1.py','tools/candidate_presence_v1/audit_presence.py',
    'tools/candidate_presence_v1/audit_scores.py','tools/candidate_presence_v1/audit_fixture.py',
    'tools/native_phase_patch_v1/audit_wave.py','tools/native_phase_patch_v1/audit_link.py',
    'tools/chirp_motion_controls_v1/audit_inputs.py','tools/native_chirp_audit_v1/wave.py',
    'tools/native_chirp_audit_v1/temporal.py','tools/research_archive_v1.py']:
    dest=a.out/'exact_sources'/name
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(repo/name,dest)
try:
    report=load(a.input/'report.json')
    assert report['result']=='all108_known_candidate_presence_windows_complete'
    assert report['prerequisite_passed'] and report['executed_windows']==108 and report['real_source_read'] is False
    for name,h in report['sources'].items():assert sha(repo/name)==h==sha(a.input/'exact_sources'/name)
    for path,h in report['parent_manifests'].items():assert sha(path)==h
    manifests={str(Path(path).parent):{v['path']:v['sha256'] for v in load(path)['files']} for path in report['parent_manifests']}
    for path,h in report['parent_files'].items():
        baseline=next(root for root in manifests if Path(path).is_relative_to(Path(root)))
        assert sha(path)==h==manifests[baseline][Path(path).relative_to(baseline).as_posix()]
    motion=a.workspace/'baselines/chirp_motion_controls_v1/evidence/observe1'
    phase=a.workspace/'baselines/phase_patch_v1/evidence/observe1'
    p0=load(motion/'report.json')['plan']
    cases=['cubic_control']+p0['cases']+['occluded_component','missing_component_neighbor','crossing_pair']
    assert [v['case'] for v in report['summaries']]==cases
    fp=load(repo/'research/accel_chirp_v1_plan.json')
    rp=load(repo/'research/accel_ridges_v1_plan.json')
    lp=load(repo/'research/low_chirp_v1_plan.json')
    qualification={}
    for case in cases:
        folder=a.input/case
        audio=np.load(folder/'signal.npz')['audio']
        truth=load(folder/'truth.json')
        if case in p0['cases']:
            error=near(audio,signal(case,p0),2e-12)
            truth_rows(case,p0,truth['rows'])
            for i,row in enumerate(truth['rows']):
                at=(i+.5)*.25
                for k,line in enumerate(row['lines']):
                    dev=p0['base_hz'][k]/p0['FM']['reference_hz']*p0['FM']['deviation_at_reference_hz']*p0['moving'][k]*(case in ['fm_only','am_fm'])
                    near(line['curvature_hz_per_second2'],-dev*(math.tau*p0['FM']['modulation_hz'])**2*math.sin(math.tau*p0['FM']['modulation_hz']*at))
                    assert line['visible']
        else:error=check_fixture(case,p0,audio,truth['rows'])
        r['maximum_signal_error']=max(r['maximum_signal_error'],error)
        obs=load(folder/'initialization.json')
        native=load(folder/'native_fits.json')
        raw=load(folder/'raw_fits.json')
        accepted=load(folder/'fits.json')
        props=load(folder/'proposals.json')
        tests=load(folder/'presence.json')
        assert len(native)==len(raw)==len(accepted)==len(props)==len(tests)==12
        initialization(obs['inventories'],obs['ratios'],obs['initial'])
        added=accepted_added=0
        for i in range(12):
            z=np.load(folder/f'tile_{i:02d}.npz')
            nz=np.load(folder/f'native_{i:02d}.npz')
            for value in [z,nz]:near(value['audio'],audio[i*12000:(i+1)*12000],0)
            scanned=inventory(nz['audio'],obs['inventories'][i],rp)
            r['maximum_peak_error']=max(r['maximum_peak_error'],scanned['error'])
            assert scanned['strongest_index']==obs['guides'][i]['native_inventory_index']
            near(scanned['strongest_hz'],obs['guides'][i]['observed_hz'],1e-8)
            near(obs['ratios'][i],obs['guides'][i]['observed_hz']/obs['guides'][0]['observed_hz'])
            previous=accepted[i-1] if i else None
            proposal(obs['inventories'][i],obs['initial'][i],previous,props[i])
            for row,array,inv,init in [(native[i],nz,obs['inventories'][i],obs['initial'][i]['initial_chirp']),
                                       (raw[i],z,props[i]['inventory'],props[i]['initial_chirp'])]:
                if not row['lines']:
                    assert row['success'] is False and row['reason']=='empty_or_overflow'
                    assert not inv['bin'] or len(inv['bin'])>64
                    continue
                m=len(row['lines'])
                near(array['nominal'],np.array(inv['bin'])*4)
                near(array['initial'][:m],np.zeros(m))
                for rate in [array['initial'][m:2*m],array['initial'][2*m:]]:near(rate,np.clip(init,-500+1e-6,500-1e-6))
                out=check_wave(array,row,fp)
                for key in ['waveform_error','support_error','normal_error','optimality_error']:
                    r['maximum_'+key]=max(r['maximum_'+key],out[key])
            if not props[i]['added_bins']:
                assert raw[i]==native[i] and set(z.files)==set(nz.files)
                for key in z.files:near(z[key],nz[key],0)
            if case=='cubic_control':
                source=phase/'cubic_control'
                assert native[i]==load(source/'fits.json')[i]
                with np.load(source/f'tile_{i:02d}.npz') as frozen:
                    assert set(frozen.files)==set(nz.files)
                    for key in frozen.files:near(nz[key],frozen[key],0)
            out=presence(z,raw[i],accepted[i],props[i],previous,tests[i])
            r['conditional_tests']+=out['tests']
            r['maximum_null_cost_error']=max(r['maximum_null_cost_error'],out['maximum_cost_error'])
            r['maximum_partial_gain_error']=max(r['maximum_partial_gain_error'],out['maximum_gain_error'])
            added+=len(props[i]['added_bins'])
            accepted_added+=sum(v['candidate_origin']=='propagated' and v['eligible'] for v in accepted[i]['lines'])
            r['windows']+=1
            r['native_lines']+=len(native[i]['lines'])
            r['raw_lines']+=len(raw[i]['lines'])
            if case=='cubic_control':
                actual=truth['rows'][i]['lines']
                reasons=[]
                if not accepted[i]['success']:reasons.append('optimizer_failure')
                if len(accepted[i]['lines'])!=10:reasons.append('mode_count')
                if not all(v['eligible'] for v in accepted[i]['lines']):reasons.append('line_eligibility')
                if len(accepted[i]['lines'])==10:
                    for name,key,limit in [('frequency','frequency_hz',.06),('rate','chirp_hz_per_second',.15),('curvature','curvature_hz_per_second2',1.2)]:
                        if max(abs(v[key]-u[key]) for v,u in zip(accepted[i]['lines'],actual))>=limit:reasons.append(name)
                relative=float(np.linalg.norm(z['residual'])/np.linalg.norm(z['audio']))
                if relative>=1e-5:reasons.append('waveform_relative_error')
                if reasons:r['prerequisite_failures'].append(dict(window=i,reasons=reasons,relative_residual=relative))
        links=load(folder/'links.json')
        expected_variants={'native_old','native_boundary','augmented_old','augmented_boundary'}
        if case in p0['cases']:expected_variants|={'previous_old','previous_boundary'}
        assert set(links)==expected_variants
        for key,linked in links.items():
            rows=native if key.startswith('native') else accepted if key.startswith('augmented') else load(motion/case/'fits.json')
            if key.endswith('_old'):audit_temporal(rows,linked,lp)
            else:check_link(rows,linked)
        if truth['rows']:check_link(truth['rows'],truth['boundary'])
        else:assert truth['boundary'] is None
        scores=load(folder/'scores.json')
        assert set(scores)==set(links)
        for key in links:check_scores(links[key],truth['rows'],scores[key])
        item=dict(case=case,windows=12,successful=sum(v['success'] for v in accepted),
            local_lines=sum(len(v['lines']) for v in accepted),eligible_lines=sum(v['eligible'] for row in accepted for v in row['lines']),
            failed_windows=[i for i,v in enumerate(accepted) if not v['success']],
            variants={key:{k:value[k] for k in ['longest_track','tracks_atleast5','components','mixed_identity_tracks','unexplained_absent_query_hits']} for key,value in scores.items()})
        assert item==next(v for v in report['summaries'] if v['case']==case)
        primary=scores['augmented_boundary']
        r['cases'].append(dict(item,added_candidates=added,accepted_added_candidates=accepted_added))
        if case in ['fm_only','am_fm']:
            qualification[case+'_all6low_atleast5']=all(v['longest_correct_contiguous']>=5 for v in primary['components'][:6])
        if case=='bandlimited_mono_noise':qualification['noise_no_track_atleast5']=primary['tracks_atleast5']==0
        if case=='occluded_component':
            assignments=primary['assignments']
            before={v['track_id'] for v in assignments if v['window']<5 and v['component']==5}
            after={v['track_id'] for v in assignments if v['window']>5 and v['component']==5}
            qualification['occluded_component_no_bridge']=not bool(before&after)
        if case in ['crossing_pair','missing_component_neighbor']:
            qualification[case+'_no_scored_switch']=not primary['mixed_identity_tracks']
        print(dict(case=case,verified_windows=12,added=added,accepted_added=accepted_added,
            low_contiguous=[v['longest_correct_contiguous'] for v in primary['components'][:6]],
            failed_windows=item['failed_windows']),flush=True)
    prereq=load(a.input/'prerequisite.json')
    assert prereq['failures']==r['prerequisite_failures']==[]
    tracks=load(a.input/'cubic_control/links.json')['augmented_boundary']['tracks']
    assert prereq['ten_complete_tracks'] and len(tracks)==10 and all(len(v['windows'])==12 for v in tracks)
    qualification['exact_cubic_prerequisite']=True
    for filename,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
        table=load(a.workspace/'baselines/idle_microtexture_c_v1/inputs'/filename)
        assert len(table)==count
        for name,h in table.items():assert sha(repo/name)==h
    r.update(result='all108_native_augmented_waveforms_proposals_conditional_nulls_graphs_scores_verified',
        input_report_sha256=sha(a.input/'report.json'),qualification=qualification,
        qualified=all(qualification.values()),real_source_read=False,C_H_unchanged=612,old_voices_unchanged=67,
        source_identity_RPM_load_or_common_phase_qualified=False)
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    raise
finally:
    save(a.out/'report.json',r)
print({key:r[key] for key in ['result','windows','native_lines','raw_lines','conditional_tests','qualification','qualified']})
