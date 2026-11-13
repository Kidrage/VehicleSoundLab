"""Attribute a fixed synthetic peak-control failure before further real analysis."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
args=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from line_motion_v1.peaks import native_peaks

args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-peak-interference/1',result='running',sources={},real_audio_read=False,
    truth_used_only_for_known_signal_diagnosis=True,model_exported=False,runtime_changed=False)
try:
    parent=args.workspace/'references/analysis/F2_native_peaks_v1/observe2/report.json'
    prior=json.loads(parent.read_text(encoding='utf-8'))
    assert prior['result']=='failed' and not prior['real_audio_read'] and not prior['controls']['passed']
    for path in (Path(__file__),*sorted((repo/'tools/line_motion_v1').glob('*.py'))):
        relative=path.relative_to(repo);target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        report['sources'][relative.as_posix()]=sha(path)
    rate=48000;time=np.arange(6*rate)/rate;phase=37.35*time+.06*time**2
    # Preserve observer input component ordering75/112/187/82/37Hz.
    components=np.array([a*np.cos(2*np.pi*n*phase+p) for n,a,p in [(2,.5,.6),(3,.4,.9),(5,.3,1.2)] ]+
        [.18*np.cos(2*np.pi*82*time+.7),.15*np.cos(2*np.pi*phase+.2)])
    nominal=[[75,112,187,82,37],[75,112,188,82,37],[76,113,189,81,38]]
    local=np.arange(rate)/rate;window=np.sin(np.pi*local)**2;derivative=np.pi*np.sin(2*np.pi*local)
    rows=[];max_operator_error=0.;max_raw_exp_error=0.
    for i,original in enumerate(prior['controls']['extended_chirp_rows']):
        start=round(original['start_seconds']*rate);parts=components[:,start:start+rate]
        mixed=parts.sum(axis=0);value=native_peaks(np.column_stack((mixed,.9*mixed)),rate,nominal[i//3])
        truth=(37.35+.12*(original['start_seconds']+.5))*np.array([2,3,5,0,1]);truth[3]=82
        errors=value['frequency_Hz'][:,0]-truth
        assert abs(float(abs(errors).max())-original['max_frequency_error_Hz'])<1e-10
        decomposition=[]
        for line,carrier in enumerate(value['frequency_Hz'][:,0]):
            kernel=np.exp(-2j*np.pi*carrier*local)
            c=(parts*window)@kernel;d=(parts*derivative)@kernel
            # Independent raw rectangle-DTFT shift identity for all25component observations.
            raw_direct=np.array([np.sum(parts*np.exp(-2j*np.pi*f*local),axis=1) for f in (carrier,carrier-1,carrier+1)])
            raw_c=.5*raw_direct[0]-.25*(raw_direct[1]+raw_direct[2])
            raw_d=np.pi/(2j)*(raw_direct[1]-raw_direct[2])
            max_raw_exp_error=max(max_raw_exp_error,float(abs(c-raw_c).max()/max(1,abs(c).max())),
                float(abs(d-raw_d).max()/max(1,abs(d).max())))
            # Factor the unit frequency shift to avoid subtracting independently
            # rounded large carrier phases when the component derivative is tiny.
            rotation=np.exp(2j*np.pi*local)
            raw=np.array([np.sum(parts*kernel*shift,axis=1) for shift in (np.ones(rate),rotation,rotation.conj())])
            alternative_c=.5*raw[0]-.25*(raw[1]+raw[2])
            alternative_d=np.pi/(2j)*(raw[1]-raw[2])
            max_operator_error=max(max_operator_error,float(abs(c-alternative_c).max()/max(1,abs(c).max())),
                                   float(abs(d-alternative_d).max()/max(1,abs(d).max())))
            contributions=-np.imag(d/c.sum())/(2*np.pi)
            assert abs(contributions.sum()-value['root_residual_Hz'][line,0])<1e-10
            solo=native_peaks(np.column_stack((parts[line],.9*parts[line])),rate,[nominal[i//3][line]])
            decomposition.append(dict(line=line,true_center_Hz=float(truth[line]),mixed_center_Hz=float(carrier),
                mixed_error_Hz=float(errors[line]),solo_error_Hz=float(solo['frequency_Hz'][0,0]-truth[line]),
                component_derivative_contributions_Hz=contributions.tolist(),
                total_root_offset_Hz=float(contributions.sum()),
                limits='Component attribution uses known synthetic stems only, never a real physical-source separation'))
        rows.append(dict(start_seconds=original['start_seconds'],per_line_error_Hz=errors.tolist(),
            passed_original_max_error=float(abs(errors).max())<=.01,decomposition=decomposition))
    report.update(rows=rows,independent_operator_relative_error=max_operator_error,
        original_direct_exponent_relative_error=max_raw_exp_error)
    assert max_operator_error<1e-10
    np.savez_compressed(args.out/'known_components.npz',components=components)
    report.update(result='known_neighbor_line_contributions_measured_not_real_frequency_qualification',
        parent_report_sha256=sha(parent),rows=rows,independent_operator_relative_error=max_operator_error,
        original_direct_exponent_gate_failure_reproduced=max_raw_exp_error>=1e-10,
        arrays_sha256=sha(args.out/'known_components.npz'),
        original_control_gate_unchanged_Hz=.01,phase_estimator_run=False,
        limits=['Known additive-component diagnosis only; no source recording read or new frequency estimate qualified',
            'A numerically accurate local root can be displaced by neighbor components; peak selection alone does not remove leakage'])
    print(json.dumps(dict(result=report['result'],errors=[dict(t=r['start_seconds'],errors=r['per_line_error_Hz']) for r in rows],
        independent_error=max_operator_error)),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
