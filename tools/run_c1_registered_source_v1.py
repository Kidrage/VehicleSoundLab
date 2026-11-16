"""Consume one paired execution intent, fit FirstLate once, audit, then stop."""
import argparse
import gc
import os
from pathlib import Path
import subprocess
import sys
import time
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from c1_registered_source_v1.binding import execution
    from c1_registered_source_v1.launch import begin
    from c1_source_adapter_v1.objective import build
    from waveform_file_real_v1.evaluate import evaluate
    from waveform_file_real_v1.resources import preflight
    from waveform_file_full_v1.pipeline import solve_full
    from waveform_file_full_v1.resources import Telemetry
    from waveform_banded_v1.metric import supported_banded
    from waveform_structured_v1.resources import process_memory
    repo = Path(__file__).resolve().parents[1]
    pair, spec = execution(a.workspace, repo, require_unlaunched=True)
    e, d = Path(pair['spec']['canonical_claim']), Path(pair['spec']['storage_claim'])
    directory = Path(spec['output'])
    assert sha(spec['input_file']) == spec['input_sha256']
    with np.load(spec['input_file']) as f:
        z = {name:f[name] for name in f.files}
    assert (len(z['audio']), len(z['target']), len(z['orders']), len(z['positions'])) == (18430, 14334, 288, 73)
    system, shared, reference = build(z)
    metric = system.metric
    for name, actual in (('probe_forward', system@z['probe_q']),
        ('probe_adjoint', system.rmatvec(z['probe_rows'])), ('probe_rhs', system.rhs(z['audio']))):
        error = float(np.max(abs(actual-z[name])))/max(1., float(np.max(abs(z[name]))))
        assert error <= 2e-12, (name, error)
    resources = preflight(d, 18430, 73, 288, 1024)
    assert resources['memory_passed'] and resources['disk_passed']
    for name in ('major_phase_panel_arithmetic', 'required_available', 'required_available_disk', 'full_factor_file_bytes'):
        assert resources[name] == spec['resource_preflight'][name]
    intent = begin(e, d)
    directory.mkdir()
    started = time.monotonic()
    r = dict(result='running', pid=os.getpid(), label=spec['only_label'],
        registration_sha256=pair['registration_sha256'], execution_spec_sha256=sha(e/'execution_spec.json'),
        measurement_identity=spec['measurement_identity'], source_identity=spec['source_identity'],
        no_automatic_next_fit_or_restart=True)
    save(directory/'report.json', r)
    save(directory/'preflight.json', resources)
    case_saved = False
    try:
        assert r['pid'] == intent['pid']
        ledger = Telemetry(directory)
        factors = directory/'factors'
        factors.mkdir()
        print('C1_REAL_PID', os.getpid(), spec['only_label'], 'N', 18430, 'M', 73, 'H', 288, flush=True)
        action = lambda error:error/metric.wave_scale**2+metric.adjoint(metric.forward(error))
        values, inverse, pipeline, initial, taus = solve_full(shared, lambda:supported_banded(metric),
            z['audio'], action, factors, ledger, 1024)
        inverse.close()
        inverse_info = inverse.info()
        outputs, stats = evaluate(system, shared, z['audio'], values, pipeline['base_solver'], reference)
        ledger.snapshot('fullPipeline.evaluated')
        z.update(values, **outputs, **taus, inverse_right_tau=inverse.right.tau,
            inverse_inner_tau=inverse.inner.tau, **{'base_'+k:v for k, v in initial.items()})
        with np.load(spec['input_file']) as original:
            for name in original.files:
                assert np.array_equal(z[name], original[name]), name
        np.savez_compressed(directory/'capture.npz', **z)
        ledger.snapshot('fullPipeline.saved')
        r.update(result='c1_registered_source_measured', frames=18430, nodes=73, orders=288, block=1024,
            pipeline=pipeline, solver=pipeline['base_solver'], inverse_info=inverse_info, **stats,
            resource_preflight=resources, resources=ledger.report(), process_memory=process_memory(),
            capture_sha256=sha(directory/'capture.npz'), prepared_file=spec['input_file'],
            prepared_sha256=spec['input_sha256'], no_full_factor_arrays_in_capture=True,
            no_sustained_or_C_or_hearing_qualification=True, elapsed_seconds_PC_only=time.monotonic()-started)
        save(directory/'report.json', r)
        case_saved = True
        ledger.progress(dict(pid=os.getpid(), status='completed', only_label=spec['only_label'],
            report_sha256=sha(directory/'report.json')))
        del z, values, inverse, outputs, system, shared, reference, initial, taus, pipeline, metric, action
        gc.collect()
        audited = d/'run1_audit'
        subprocess.run([sys.executable, str(repo/'tools/audit_c1_registered_source_v1.py'),
            '--workspace', str(a.workspace), '--study', str(directory), '--out', str(audited)], check=True, cwd=repo)
        result = load(audited/'report.json')
        assert result['verification_passed']
        save(d/'execution_result.json', dict(result='c1_registered_single_run_complete', pid=os.getpid(),
            case_report_sha256=sha(directory/'report.json'), audit_report_sha256=sha(audited/'report.json'),
            solver_qualified=result['case']['solver_qualified'], fidelity_qualified=result['case']['fidelity_qualified'],
            no_automatic_next_fit_or_restart=True, no_C_or_sustained_or_hearing_promotion=True))
        print('C1_REAL_COMPLETE', result['case']['solver_qualified'], result['case']['fidelity_qualified'], flush=True)
    except BaseException as error:
        failed = dict(result='failed', pid=os.getpid(), error=repr(error),
            elapsed_seconds_PC_only=time.monotonic()-started, case_capture_preserved=case_saved,
            no_restart_or_next_fit=True)
        save(d/'execution_result.json', failed)
        if not case_saved:
            save(directory/'report.json', dict(r, **failed))
        raise


if __name__ == '__main__':
    main()
