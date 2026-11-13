"""Independent all48 F3 native/augmentation/prediction/source observation audit."""
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
from native_chirp_audit_v1.temporal import audit_temporal,audit_predictions
from chirp_motion_controls_v1.audit_inputs import inventory,initialization
from native_phase_patch_v1.audit_wave import check as check_wave
from native_phase_patch_v1.audit_link import check as check_link
from candidate_presence_v1.audit_presence import proposal,presence
from candidate_prediction_v1.audit_fit import check as check_verification
from candidate_prediction_v1.audit_decision import check as check_decision
from accel_candidate_prediction_v1.coverage import known_controls as coverage_controls,describe as coverage_describe

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',windows=0,native_lines=0,raw_lines=0,selected_lines=0,verification_fits=0,verification_lines=0,
    conditional_tests=0,prediction_tests=0,prediction_supported=0,prediction_unknown=0,adopted_windows=0,
    maximum_input_error=0.,maximum_peak_error=0.,maximum_waveform_error=0.,maximum_support_error=0.,
    maximum_normal_error=0.,maximum_optimality_error=0.,maximum_verification_waveform_error=0.,
    maximum_verification_normal_error=0.,maximum_verification_optimality_error=0.,maximum_verification_cost_error=0.,
    maximum_null_cost_error=0.,maximum_null_gain_error=0.,observations=[],spectral_coverage={})
names=['tools/audit_accel_candidate_prediction_v1.py','tools/research_archive_v1.py',
    'tools/accel_candidate_prediction_v1/coverage.py','research/accel_candidate_prediction_v1_coverage_plan.json',
    'tools/chirp_motion_controls_v1/audit_inputs.py','tools/native_chirp_audit_v1/wave.py','tools/native_chirp_audit_v1/temporal.py']
names += [v.relative_to(repo).as_posix() for directory in ['native_phase_patch_v1','candidate_presence_v1','candidate_prediction_v1']
          for v in (repo/'tools'/directory).glob('audit*.py')]
for name in names:
    dest=a.out/'exact_sources'/name
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(repo/name,dest)
try:
    coverage_plan=load(repo/'research/accel_candidate_prediction_v1_coverage_plan.json')
    r['coverage_controls']=coverage_controls(coverage_plan['bands_hz'])
    r['coverage_bands_hz']=coverage_plan['bands_hz']
    report=load(a.input/'report.json')
    assert report['result']=='all48_original_F3_cubic_candidate_prediction_observations_complete'
    assert report['native_windows_completed']==report['selected_windows_completed']==48 and report['real_source_read']
    for name,h in report['sources'].items():assert sha(repo/name)==h==sha(a.input/'exact_sources'/name)
    tables={}
    for path,h in report['parent_manifests'].items():
        assert sha(path)==h
        tables[str(Path(path).parent)]={v['path']:v['sha256'] for v in load(path)['files']}
    for path,h in report['parent_files'].items():
        base=next(root for root in tables if Path(path).is_relative_to(root))
        assert sha(path)==h==tables[base][Path(path).relative_to(base).as_posix()]
    known=a.workspace/'baselines/candidate_prediction_v1'
    assert load(known/'evidence/audit2/report.json')['qualified_known_controls']
    for name in ['tools/native_phase_patch_v1/fit.py','tools/native_phase_patch_v1/basis.py','tools/native_phase_patch_v1/link.py',
        'tools/candidate_presence_v1/propose.py','tools/candidate_presence_v1/presence.py',
        'tools/candidate_prediction_v1/fit.py','tools/candidate_prediction_v1/decision.py']:
        assert sha(repo/name)==sha(known/'source'/name)
    source_root=a.workspace/'baselines/accel_low_fit_v1/evidence/observe2'
    old_root=a.workspace/'baselines/accel_low_profiled_v1/evidence/observe1'
    fp=load(repo/'research/accel_chirp_v1_plan.json')
    rp=load(repo/'research/accel_ridges_v1_plan.json')
    lp=load(repo/'research/low_chirp_v1_plan.json')
    cases=['F3_fifth1','F3_fifth2','F3_sixth']
    assert [v['segment'] for v in report['observations']]==cases
    for case in cases:
        folder=a.input/case
        source=source_root/case
        old_source=old_root/case
        obs=load(folder/'initialization.json')
        originals=load(folder/'original_linear_fits.json')
        old=load(folder/'profiled_linear_fits.json')
        assert obs==load(source/'initialization.json') and originals==load(source/'fits.json') and old==load(old_source/'fits.json')
        native=load(folder/'native_fits.json')
        raw=load(folder/'raw_fits.json')
        postfits=load(folder/'augmented_accepted_fits.json')
        rows=load(folder/'fits.json')
        proposals=load(folder/'proposals.json')
        tests=load(folder/'presence.json')
        verifications=load(folder/'verification_fits.json')
        decisions=load(folder/'decisions.json')
        audio=np.load(folder/'signal.npz')['audio']
        count=len(originals)
        assert len(native)==len(raw)==len(postfits)==len(rows)==len(proposals)==len(tests)==len(verifications)==len(decisions)==count
        initialization(obs['inventories'],[v['ratio'] for v in originals],obs['initial'])
        for i in range(count):
            previous=rows[i-1] if i else None
            nz=np.load(folder/f'native_{i:02d}.npz')
            z=np.load(folder/f'tile_{i:02d}.npz')
            chosen=np.load(folder/f'selected_{i:02d}.npz')
            original_audio=np.load(source/f'tile_{i:02d}.npz')['audio']
            for value in [nz,z,chosen]:r['maximum_input_error']=max(r['maximum_input_error'],near(value['audio'],original_audio,0))
            near(audio[i*12000:(i+1)*12000],original_audio,0)
            scanned=inventory(original_audio,obs['inventories'][i],rp)
            r['maximum_peak_error']=max(r['maximum_peak_error'],scanned['error'])
            for value in [native[i],raw[i],rows[i]]:
                assert value['tile']==i and value['ratio']==originals[i]['ratio'] and value['guide_supported']==originals[i]['guide_supported']
            proposal(obs['inventories'][i],obs['initial'][i],previous,proposals[i])
            for row,array,inv,init in [(native[i],nz,obs['inventories'][i],obs['initial'][i]['initial_chirp']),
                                      (raw[i],z,proposals[i]['inventory'],proposals[i]['initial_chirp'])]:
                if not row['lines']:
                    assert row['success'] is False and row['reason']=='empty_or_overflow' and (not inv['bin'] or len(inv['bin'])>64)
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
                    near(vz['audio'],original_audio,0)
                    out=check_verification(vz,row,nominal,chirp)
                    r['verification_fits']+=1
                    r['verification_lines']+=out['lines']
                    for key in ['waveform_error','normal_error','optimality_error','cost_error']:r['maximum_verification_'+key]=max(r['maximum_verification_'+key],out[key])
            else:
                assert verification==dict(present=None,deleted={}) and raw[i]==native[i]
                assert set(z.files)==set(nz.files)
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
            save(a.out/'report.json',r)
            print(dict(segment=case,window=i,verified=r['windows'],added=len(proposals[i]['added_bins']),decision=decisions[i]['reason']),flush=True)
        links=load(folder/'links.json')
        predicted=load(folder/'predictions.json')
        assert set(links)==set(predicted)=={'profiled_old','profiled_boundary','native_old','native_boundary','selected_old','selected_boundary'}
        assert links['profiled_old']==load(old_source/'temporal.json')
        for key,linked in links.items():
            value=old if key.startswith('profiled') else native if key.startswith('native') else rows
            if key.endswith('_old'):audit_temporal(value,linked,lp)
            else:check_link(value,linked)
            audit_predictions(value,linked,predicted[key])
        item=dict(segment=case,windows=count,native_successful=sum(v['success'] for v in native),
            augmented_attempts=sum(bool(v['added_bins']) for v in proposals),selected_successful=sum(v['success'] for v in rows),
            native_lines=sum(len(v['lines']) for v in native),raw_lines=sum(len(v['lines']) for v in raw),
            selected_lines=sum(len(v['lines']) for v in rows),selected_eligible=sum(v['eligible'] for row in rows for v in row['lines']),
            adopted_windows=[i for i,v in enumerate(decisions) if v['augmented_adopted']],
            unknown_windows=[i for i,v in enumerate(decisions) if v['reason']=='augmentation_unknown'],
            variants={key:dict(longest_low_start_track=max((len(v['windows']) for v in value['tracks'] if v['frequencies_hz'][0]<200),default=0),
                low_start_tracks_atleast5=sum(v['frequencies_hz'][0]<200 and len(v['windows'])>=5 for v in value['tracks']),
                compared_low_tracks=sum(v['status']=='compared' for v in predicted[key])) for key,value in links.items()})
        assert item==next(v for v in report['observations'] if v['segment']==case)
        r['observations'].append(item)
        coverage=coverage_describe(folder,native,obs['inventories'],coverage_plan['bands_hz'])
        save(a.out/(case+'_coverage.json'),coverage)
        r['spectral_coverage'][case]={key:value for key,value in coverage.items() if key!='rows'}
    for filename,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
        values=load(a.workspace/'baselines/idle_microtexture_c_v1/inputs'/filename)
        assert len(values)==count
        for name,h in values.items():assert sha(repo/name)==h
    assert r['windows']==48
    r.update(result='all48_F3_native_augmented_masked_predictions_adoption_graphs_verified',
        input_report_sha256=sha(a.input/'report.json'),C_H_unchanged=612,old_voices_unchanged=67,
        input_candidates_and_neighbor_conditioned_not_pristine_holdout=True,
        physical_source_RPM_load_or_common_phase_identified=False,new_audio_profile_or_runtime=False)
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    raise
finally:save(a.out/'report.json',r)
print({key:r[key] for key in ['result','windows','native_lines','raw_lines','selected_lines','verification_fits','verification_lines','prediction_tests','prediction_supported','prediction_unknown','adopted_windows']})
