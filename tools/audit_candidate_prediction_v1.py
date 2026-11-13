"""Independent full-wave, withheld-parameter prediction and adoption qualification."""
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
from scipy.linalg import lstsq
from research_archive_v1 import load,save,sha
from native_chirp_audit_v1.wave import near
from native_chirp_audit_v1.temporal import audit_temporal
from chirp_motion_controls_v1.audit_inputs import signal,truth_rows,inventory,initialization
from native_phase_patch_v1.audit_wave import check as check_wave
from native_phase_patch_v1.audit_link import check as check_link
from candidate_presence_v1.audit_presence import proposal,presence
from candidate_presence_v1.audit_scores import check as check_scores
from candidate_presence_v1.audit_fixture import check as check_fixture
from candidate_prediction_v1.audit_fit import check as check_verification
from candidate_prediction_v1.audit_decision import check as check_decision

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',windows=0,native_lines=0,raw_lines=0,selected_lines=0,verification_fits=0,verification_lines=0,
    conditional_tests=0,prediction_tests=0,prediction_supported=0,prediction_unknown=0,adopted_windows=0,
    maximum_signal_error=0.,maximum_peak_error=0.,maximum_waveform_error=0.,maximum_support_error=0.,
    maximum_normal_error=0.,maximum_optimality_error=0.,maximum_verification_waveform_error=0.,
    maximum_verification_normal_error=0.,maximum_verification_optimality_error=0.,maximum_verification_cost_error=0.,
    maximum_null_cost_error=0.,maximum_null_gain_error=0.,prerequisite_failures=[],cases=[])
names=['tools/audit_candidate_prediction_v1.py','tools/research_archive_v1.py',
    'tools/chirp_motion_controls_v1/audit_inputs.py','tools/native_chirp_audit_v1/wave.py','tools/native_chirp_audit_v1/temporal.py']
names += [v.relative_to(repo).as_posix() for directory in ['native_phase_patch_v1','candidate_presence_v1','candidate_prediction_v1']
          for v in (repo/'tools'/directory).glob('audit*.py')]
for name in names:
    dest=a.out/'exact_sources'/name
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(repo/name,dest)
try:
    report=load(a.input/'report.json')
    assert report['result']=='all108_known_full_candidate_prediction_windows_complete'
    assert report['executed_windows']==108 and report['prerequisite_passed'] and report['real_source_read'] is False
    for name,h in report['sources'].items():assert sha(repo/name)==h==sha(a.input/'exact_sources'/name)
    baseline=a.workspace/'baselines/candidate_presence_v1'
    assert sha(baseline/'manifest.json')==report['parent_manifest_sha256']
    table={v['path']:v['sha256'] for v in load(baseline/'manifest.json')['files']}
    for name,h in report['parent_files'].items():assert sha(baseline/name)==h==table[name]
    parent_root=baseline/'evidence/observe1'
    motion=a.workspace/'baselines/chirp_motion_controls_v1/evidence/observe1'
    p0=load(motion/'report.json')['plan']
    cases=['cubic_control']+p0['cases']+['occluded_component','missing_component_neighbor','crossing_pair']
    assert [v['case'] for v in report['summaries']]==cases
    fp=load(repo/'research/accel_chirp_v1_plan.json')
    rp=load(repo/'research/accel_ridges_v1_plan.json')
    lp=load(repo/'research/low_chirp_v1_plan.json')
    control=np.load(a.input/'projection_control.npz')
    nominal,point,t,w,x=[control[k] for k in ['nominal','point','time','weight','audio']]
    near(w,np.sqrt(np.hanning(12001)[:-1]/12000)*(np.arange(12000)<9000),1e-16)
    def independent_residual(p):
        m=len(nominal)
        f=nominal+p[:m]
        q=(p[m:2*m]+p[2*m:])/2
        c=(p[2*m:]-p[m:2*m])/.25
        z=np.exp(1j*math.tau*(t[:,None]*f+t[:,None]**2*q/2+t[:,None]**3*c/6))
        matrix=w[:,None]*np.column_stack((z.real,z.imag,np.ones(len(t))))
        co=lstsq(matrix,w*x,lapack_driver='gelsd')[0]
        return matrix@co-w*x
    near(independent_residual(point),control['residual'],1e-12)
    near(independent_residual(point),control['SVD_residual'],1e-12)
    numeric=[]
    for j in range(9):
        step=np.zeros(9)
        step[j]=1e-5
        numeric.append((independent_residual(point+step)-independent_residual(point-step))/2e-5)
    r['independent_masked_Jacobian_error']=near(np.column_stack(numeric),control['analytic'],1e-8)
    qualification={}
    for case in cases:
        folder=a.input/case
        source=parent_root/case
        audio=np.load(folder/'signal.npz')['audio']
        near(audio,np.load(source/'signal.npz')['audio'],0)
        truth=load(folder/'truth.json')
        assert truth==load(source/'truth.json')
        if case in p0['cases']:
            error=near(audio,signal(case,p0),2e-12)
            truth_rows(case,p0,truth['rows'])
            for i,row in enumerate(truth['rows']):
                for k,line in enumerate(row['lines']):
                    at=(i+.5)*.25
                    dev=p0['base_hz'][k]/p0['FM']['reference_hz']*p0['FM']['deviation_at_reference_hz']*p0['moving'][k]*(case in ['fm_only','am_fm'])
                    near(line['curvature_hz_per_second2'],-dev*(math.tau*p0['FM']['modulation_hz'])**2*math.sin(math.tau*p0['FM']['modulation_hz']*at))
                    assert line['visible']
        else:error=check_fixture(case,p0,audio,truth['rows'])
        r['maximum_signal_error']=max(r['maximum_signal_error'],error)
        obs=load(folder/'initialization.json')
        native=load(folder/'native_fits.json')
        assert obs==load(source/'initialization.json') and native==load(source/'native_fits.json')
        raw=load(folder/'raw_fits.json')
        postfits=load(folder/'augmented_accepted_fits.json')
        rows=load(folder/'fits.json')
        proposals=load(folder/'proposals.json')
        tests=load(folder/'presence.json')
        verifications=load(folder/'verification_fits.json')
        decisions=load(folder/'decisions.json')
        assert len(raw)==len(postfits)==len(rows)==len(proposals)==len(tests)==len(verifications)==len(decisions)==12
        initialization(obs['inventories'],obs['ratios'],obs['initial'])
        for i in range(12):
            previous=rows[i-1] if i else None
            nz=np.load(source/f'native_{i:02d}.npz')
            z=np.load(folder/f'tile_{i:02d}.npz')
            chosen=np.load(folder/f'selected_{i:02d}.npz')
            for value in [nz,z,chosen]:near(value['audio'],audio[i*12000:(i+1)*12000],0)
            scanned=inventory(nz['audio'],obs['inventories'][i],rp)
            r['maximum_peak_error']=max(r['maximum_peak_error'],scanned['error'])
            assert scanned['strongest_index']==obs['guides'][i]['native_inventory_index']
            near(scanned['strongest_hz'],obs['guides'][i]['observed_hz'],1e-8)
            near(obs['ratios'][i],obs['guides'][i]['observed_hz']/obs['guides'][0]['observed_hz'])
            proposal(obs['inventories'][i],obs['initial'][i],previous,proposals[i])
            for row,array,inv,init in [(native[i],nz,obs['inventories'][i],obs['initial'][i]['initial_chirp']),
                                      (raw[i],z,proposals[i]['inventory'],proposals[i]['initial_chirp'])]:
                if not row['lines']:
                    assert row['success'] is False and row['reason']=='empty_or_overflow'
                    assert not inv['bin'] or len(inv['bin'])>64
                    continue
                m=len(row['lines'])
                near(array['nominal'],np.array(inv['bin'])*4)
                near(array['initial'][:m],np.zeros(m))
                for part in [array['initial'][m:2*m],array['initial'][2*m:]]:near(part,np.clip(init,-500+1e-6,500-1e-6))
                out=check_wave(array,row,fp)
                for key in ['waveform_error','support_error','normal_error','optimality_error']:r['maximum_'+key]=max(r['maximum_'+key],out[key])
            out=presence(z,raw[i],postfits[i],proposals[i],previous,tests[i])
            r['conditional_tests']+=out['tests']
            r['maximum_null_cost_error']=max(r['maximum_null_cost_error'],out['maximum_cost_error'])
            r['maximum_null_gain_error']=max(r['maximum_null_gain_error'],out['maximum_gain_error'])
            verification=verifications[i]
            if proposals[i]['added_bins']:
                assert set(verification['deleted'])==set(map(str,proposals[i]['added_bins']))
                nominal=np.array(proposals[i]['inventory']['bin'])*4
                chirp=np.array(proposals[i]['initial_chirp'])
                fits=[(verification['present'],folder/f'verify_present_{i:02d}.npz',nominal,chirp)]
                for cell in proposals[i]['added_bins']:
                    keep=np.array([v!=cell for v in proposals[i]['inventory']['bin']])
                    fits.append((verification['deleted'][str(cell)],folder/f'verify_deleted_{i:02d}_{cell:04d}.npz',nominal[keep],chirp[keep]))
                for row,path,nominal,chirp in fits:
                    vz=np.load(path)
                    near(vz['audio'],nz['audio'],0)
                    out=check_verification(vz,row,nominal,chirp)
                    r['verification_fits']+=1
                    r['verification_lines']+=out['lines']
                    for key in ['waveform_error','normal_error','optimality_error','cost_error']:
                        r['maximum_verification_'+key]=max(r['maximum_verification_'+key],out[key])
            else:
                assert verification==dict(present=None,deleted={})
                assert raw[i]==native[i] and set(z.files)==set(nz.files)
                for key in z.files:near(z[key],nz[key],0)
            out=check_decision(native[i],raw[i],postfits[i],rows[i],proposals[i],verification,decisions[i])
            r['prediction_tests']+=out['added']
            r['prediction_supported']+=out['supported']
            r['prediction_unknown']+=out['unknown']
            r['adopted_windows']+=out['adopted']
            expected=z if out['adopted'] else nz
            assert set(chosen.files)==set(expected.files)
            for key in chosen.files:near(chosen[key],expected[key],0)
            r['windows']+=1
            r['native_lines']+=len(native[i]['lines'])
            r['raw_lines']+=len(raw[i]['lines'])
            r['selected_lines']+=len(rows[i]['lines'])
            if case=='cubic_control':
                reasons=[]
                if not rows[i]['success']:reasons.append('optimizer_failure')
                if len(rows[i]['lines'])!=10:reasons.append('mode_count')
                if not all(v['eligible'] for v in rows[i]['lines']):reasons.append('line_eligibility')
                if len(rows[i]['lines'])==10:
                    for name,key,limit in [('frequency','frequency_hz',.06),('rate','chirp_hz_per_second',.15),('curvature','curvature_hz_per_second2',1.2)]:
                        if max(abs(v[key]-u[key]) for v,u in zip(rows[i]['lines'],truth['rows'][i]['lines']))>=limit:reasons.append(name)
                relative=float(np.linalg.norm(chosen['residual'])/np.linalg.norm(chosen['audio']))
                if relative>=1e-5:reasons.append('waveform_relative_error')
                if reasons:r['prerequisite_failures'].append(dict(window=i,reasons=reasons,relative_residual=relative))
        links=load(folder/'links.json')
        required={'native_old','native_boundary','unscreened_old','unscreened_boundary','selected_old','selected_boundary'}
        if case in p0['cases']:required|={'previous_old','previous_boundary'}
        assert set(links)==required
        for key,linked in links.items():
            value=native if key.startswith('native') else rows if key.startswith('selected') else (
                load(source/'fits.json') if key.startswith('unscreened') else load(motion/case/'fits.json'))
            if key.endswith('_old'):audit_temporal(value,linked,lp)
            else:check_link(value,linked)
        if truth['rows']:check_link(truth['rows'],truth['boundary'])
        else:assert truth['boundary'] is None
        scores=load(folder/'scores.json')
        assert set(scores)==set(links)
        for key in scores:check_scores(links[key],truth['rows'],scores[key])
        item=dict(case=case,windows=12,successful=sum(v['success'] for v in rows),
            local_lines=sum(len(v['lines']) for v in rows),eligible_lines=sum(v['eligible'] for row in rows for v in row['lines']),
            selected_failed_windows=[i for i,v in enumerate(rows) if not v['success']],
            augmented_adopted_windows=[i for i,v in enumerate(decisions) if v['augmented_adopted']],
            augmentation_unknown_windows=[i for i,v in enumerate(decisions) if v['reason']=='augmentation_unknown'],
            variants={key:{k:v[k] for k in ['longest_track','tracks_atleast5','components','mixed_identity_tracks','unexplained_absent_query_hits']} for key,v in scores.items()})
        assert item==next(v for v in report['summaries'] if v['case']==case)
        primary=scores['selected_boundary']
        if case in ['fm_only','am_fm']:qualification[case+'_all6low_atleast5']=all(v['longest_correct_contiguous']>=5 for v in primary['components'][:6])
        if case=='bandlimited_mono_noise':qualification['noise_no_track_atleast5']=primary['tracks_atleast5']==0
        if case=='occluded_component':
            assignments=primary['assignments']
            before={v['track_id'] for v in assignments if v['window']<5 and v['component']==5}
            after={v['track_id'] for v in assignments if v['window']>5 and v['component']==5}
            qualification['occluded_component_no_bridge']=not bool(before&after)
        if case in ['missing_component_neighbor','crossing_pair']:qualification[case+'_no_scored_switch']=not primary['mixed_identity_tracks']
        r['cases'].append(item)
        save(a.out/'report.json',r)
        print(dict(case=case,verified=12,low_correct_runs=[v['longest_correct_contiguous'] for v in primary['components'][:6]],
            adopted=item['augmented_adopted_windows'],unknown=item['augmentation_unknown_windows'],failed=item['selected_failed_windows']),flush=True)
    prerequisite=load(a.input/'prerequisite.json')
    assert prerequisite['failures']==r['prerequisite_failures']==[] and prerequisite['passed']
    tracks=load(a.input/'cubic_control/links.json')['selected_boundary']['tracks']
    assert prerequisite['ten_complete_tracks'] and len(tracks)==10 and all(len(v['windows'])==12 for v in tracks)
    qualification['exact_cubic_prerequisite']=True
    for filename,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
        values=load(a.workspace/'baselines/idle_microtexture_c_v1/inputs'/filename)
        assert len(values)==count
        for name,h in values.items():assert sha(repo/name)==h
    r.update(result='all108_full_masked_predictions_adoption_graphs_and_scores_independently_verified',
        input_report_sha256=sha(a.input/'report.json'),qualification=qualification,qualified_known_controls=all(qualification.values()),
        conditioned_candidates_not_pristine_holdout=True,original_common_phase_qualification_not_waived=True,
        C_H_unchanged=612,old_voices_unchanged=67,real_source_read=False,new_audio_or_profile=False)
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    raise
finally:save(a.out/'report.json',r)
print({key:r[key] for key in ['result','windows','raw_lines','selected_lines','verification_fits','verification_lines','prediction_tests','prediction_supported','prediction_unknown','qualification','qualified_known_controls']})
