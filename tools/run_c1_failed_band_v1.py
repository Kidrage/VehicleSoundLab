"""Reuse qualified observers, then diagnose one saved terminal C1 failure."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from c1_failed_band_v1.known import qualify
    from c1_failed_band_v1.measure import analyze
    from c1_native_diagnostics_v1.input import terminal
    from c1_registered_source_v1.binding import protected
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',schema='vsl.c1-failed-band-diagnostic/1',sources={},inputs={})
    def consume(path):r['inputs'][str(path)]=sha(path);return load(path)
    try:
        protected(a.workspace,repo)
        for name in ('research/c1_failed_band_v1_plan.json','tools/run_c1_failed_band_v1.py','tools/audit_c1_failed_band_v1.py',
            'tools/c1_failed_band_v1/__init__.py','tools/c1_failed_band_v1/clock.py','tools/c1_failed_band_v1/known.py',
            'tools/c1_failed_band_v1/measure.py','tools/c1_native_diagnostics_v1/input.py',
            'tools/locked_source_error_v1/assessment.py','tools/locked_source_guard_v1/measurement.py','tools/research_archive_v1.py'):
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        prior=a.workspace/'references/analysis/locked_source_error_v1'
        old=consume(prior/'review1/report.json');old_audit=consume(prior/'review_audit1/report.json')
        assert old['result']=='locked_source_error_assessment_published' and old['known']['passed']
        assert old_audit['verification_passed'] and old_audit['producer_sha256']==sha(prior/'review1/report.json')
        for name in ('tools/locked_source_error_v1/assessment.py','tools/locked_source_guard_v1/measurement.py'):
            assert old['sources'][name]==sha(repo/name)==sha(prior/'review1/exact_sources'/name)
        assert old['known_gain']['all_ten_groups'] and old['known_gain']['maximum_metric_error']<2e-12
        r['known']=qualify();r['qualified_observer_reused_without_rerun']=True;save(a.out/'report.json',r)
        registration=consume(a.workspace/'references/analysis/c1_fit_registration_v1/registration1/report.json')
        claim=Path(registration['pair']['spec']['storage_claim'])
        z,binding=terminal(claim/'run1',claim/'run1_audit',workspace=a.workspace)
        r['inputs'].update(binding['inputs']);r['source']=binding
        actual=load(claim/'run1/report.json');audit=load(claim/'run1_audit/report.json')
        assert not actual['fidelity_qualified'] and not audit['case']['fidelity_qualified']
        assert binding['label']=='F3 Fifth First Late' and not binding['eligible_for_later_source_statistics']
        gap=max(actual['residual_certificate']['gap_upper_bound'],audit['case']['residual_certificate']['gap_upper_bound'])
        arrays,summary=analyze(z,dict(gap_upper_bound=gap))
        summary['nominal_original_optimality'].update(
            gap_is_maximum_of_declared_and_independent_audit=True,
            declared_gap_upper_bound=actual['residual_certificate']['gap_upper_bound'],
            independent_gap_upper_bound=audit['case']['residual_certificate']['gap_upper_bound'])
        got=[row['combined_complex_NRMSE'] for row in summary['original_bands']]
        expected=actual['metrics']['target_supported_band_complex_NRMSE']
        assert np.max(abs(np.array(got)-expected))<2e-12
        native=a.workspace/'references/analysis/c1_native_review_v1'
        previous=consume(native/'review1/report.json');proof=consume(native/'audit1/report.json')
        assert previous['verification_passed'] and proof['verification_passed']
        assert proof['producer_sha256']==sha(native/'review1/report.json')
        measured=native/'review1/measured.npz';assert sha(measured)==previous['files']['measured.npz'];r['inputs'][str(measured)]=sha(measured)
        with np.load(measured) as f:
            for name in ('frequency','starts','bin_component_Gram','bin_error_power','raw_bin_power','filtered_bin_power','source_grid_bin_power','candidate_bin_power'):
                arrays['native_'+name]=f[name]
        np.savez_compressed(a.out/'diagnostic.npz',**arrays)
        r.update(result='single_terminal_c1_failed_band_diagnosed',summary=summary,
            native_bands_reused=previous['bands'],native_label=previous['label'],
            native_frames=previous['native_frames'],native_start_seconds=previous['native_start_seconds'],
            original_all_metrics=actual['metrics'],original_fidelity_gate=.02,
            original_calibration=dict(weights_sha256_of_array=hashlib.sha256(z['weights'].tobytes()).hexdigest(),
                band_power=z['band_power'].tolist(),floor_active=z['floor_active'].tolist(),
                amplitude=float(z['amplitude']),sigma=float(z['sigma'])),
            original_fidelity_qualified=False,eligible_for_later_source_statistics=False,
            direct_continuous_OSC_measured=False,no_new_native_reconstruction=True,
            no_fit_restart_training_audio_C_driver_room_default_or_hearing_change=True,
            no_audio_or_mechanical_cause_identified=True,arrays_sha256=sha(a.out/'diagnostic.npz'),full_goal='ACTIVE')
        save(a.out/'report.json',r);print(r['result'],'highest',got[-1],
            'above_error_fraction',summary['above_centre_error_fraction_of_highest_weighted_mass'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
