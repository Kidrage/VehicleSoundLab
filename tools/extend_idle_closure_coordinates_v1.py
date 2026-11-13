"""Explicit second-coordinate diagnostic, preserving the original completed study."""
import argparse
import shutil
import sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'input', 'out']: p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load, save, sha
from idle_closure_evidence_v1.observe import observe, arc_membership, FREQUENCIES, ORIGINS

a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_extension.py')
plan_path = repo/'research/idle_closure_coordinates_v1_extension.json'; shutil.copy2(plan_path, a.out/'executed_extension_plan.json')
r = dict(result='running', observations=[])
try:
    # Algebraic controls before real phase-array access.
    theta = np.arange(30000)[:, None]*np.array([[.00071, .00113, .00219]])+np.array([.2, -.4, .7])
    z = np.exp(1j*theta); w = z[:, 0]**3*z[:, 1].conj()**2
    error = float(abs(w-np.exp(1j*(3*theta[:, 0]-2*theta[:, 1]))).max()); assert error < 1e-12
    d = np.array([.1, -.3, .7]); zz = z*np.exp(1j*d)
    assert abs(zz[:, 0]**3*zz[:, 1].conj()**2-w*np.exp(1j*(3*d[0]-2*d[1]))).max() < 1e-12
    r['known'] = dict(algebra_error=error, independent_origin=True)
    parent = load(a.input/'report.json'); assert parent['result'] == 'all8_closure_portions_and_shortrecord_counterexample_observed'
    rows = {}; arrays = {}; phase = {}
    for prior in parent['observations']:
        with np.load(a.input/prior['file']) as archive: z = archive['phasors']; phase[prior['label']] = archive['closure']
        w = z[:, 0]**3*z[:, 1].conj()**2
        stats, values = observe(np.column_stack((np.ones(len(w), complex), np.ones(len(w), complex), w)))
        output = a.out/(prior['label']+'.npz'); np.savez_compressed(output, **values)
        row = dict(label=prior['label'], group=prior['group'], part=prior['part'], file=output.name, sha256=sha(output), **stats)
        r['observations'].append(row); rows[row['label']] = row; arrays[row['label']] = values['closure']
    eta = arc_membership(arrays['source_check'], rows['source_train'])
    psi_train = next(x for x in parent['observations'] if x['label'] == 'source_train')
    psi_check = arc_membership(phase['source_check'], psi_train)
    with np.load(a.input/parent['runtime_arc_file']) as archive: t = archive['time_seconds']; psi_runtime = archive['inside_train_arc']
    freq = float(3*FREQUENCIES[0]-2*FREQUENCIES[1]); initial = float(3*ORIGINS[0]-2*ORIGINS[1])
    runtime_w = np.exp(1j*(initial+2*np.pi*freq*t)); inside = arc_membership(runtime_w, rows['source_train'])
    joint = inside & psi_runtime if inside is not None else None
    path = a.out/'runtime_eta.npz'; np.savez_compressed(path, closure=runtime_w,
        inside_train_arc=np.array([], bool) if inside is None else inside,
        inside_joint_rectangle=np.array([], bool) if joint is None else joint)
    r.update(result='second_coordinate_and_joint_support_observed_NO_generation', plan=load(plan_path),
        input_report_sha256=sha(a.input/'report.json'), eta_frequency_hz=freq, eta_period_seconds=1/abs(freq),
        source_eta_check_coverage=None if eta is None else float(eta.mean()),
        source_joint_check_coverage=None if eta is None or psi_check is None else float((eta & psi_check).mean()),
        runtime_eta_coverage=None if inside is None else float(inside.mean()),
        runtime_eta_first12_coverage=None if inside is None else float(inside[:12000].mean()),
        runtime_joint_coverage=None if joint is None else float(joint.mean()),
        runtime_joint_first12_coverage=None if joint is None else float(joint[:12000].mean()),
        runtime_file=path.name, runtime_sha256=sha(path), runtime_changed=False, audio_generated=False)
except Exception as exc: r.update(result='failed', error=repr(exc)); raise
finally: save(a.out/'report.json', r)
print(dict(result=r['result'], eta_hz=r.get('eta_frequency_hz'), eta_period=r.get('eta_period_seconds'),
           source_joint=r.get('source_joint_check_coverage'), runtime_joint=r.get('runtime_joint_coverage'),
           runtime_first12joint=r.get('runtime_joint_first12_coverage')), flush=True)
