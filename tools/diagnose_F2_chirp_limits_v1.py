"""Known-only flat chirp-bound clipping and conditional3Hz residual diagnostic."""
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
from line_motion_v1.chirp_limit_controls import fixtures
from line_motion_v1.peaks import native_peaks
from line_motion_v1.local_chirps import fit_channel,evaluate
from line_motion_v1.sideband_subspaces import observe


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-chirp-limits/1',result='running',sources={},real_audio_read=False,
    model_exported=False,runtime_changed=False,shared_phase_clock_fit=False,truth_used_as_phase_fit_initialization=False)
try:
    for path in (Path(__file__),repo/'research/F2_chirp_limits_v1_plan.json',repo/'tools/drive_evidence_v1/sources.py',
        *sorted((repo/'tools/line_motion_v1').glob('*.py'))):
        relative=path.relative_to(repo);target=args.out/'exact_sources'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target);report['sources'][relative.as_posix()]=sha(path)
    t=np.arange(48000)/48000-.5;rows=[];arrays={}
    for case in fixtures():
        raw=native_peaks(np.column_stack((case['audio'],case['audio'])),48000,case['labels'])
        nominal=raw['selected_native_bin_Hz'][:,0].astype(float);assert np.all(nominal>=0)
        parameters,fit=fit_channel(case['audio'],48000,nominal);m=len(nominal)
        old=evaluate(parameters,nominal,t)[0];central=parameters[2*m:3*m]-1j*parameters[3*m:4*m]
        waves,subspace=observe(case['audio'],nominal+parameters[:m],parameters[m:2*m],central,t)
        # Known-coordinate operator contract; no truth passed into fit_channel.
        truth_waves,truth_spaces=observe(case['audio'],case['frequency'],case['chirp'],case['central'],t)
        relative=float(np.linalg.norm(old-case['audio'])/np.linalg.norm(case['audio']))
        frequency_error=float(abs(nominal+parameters[:m]-case['frequency']).max())
        truth_relative=float(np.linalg.norm(truth_waves['base']-case['audio'])/np.linalg.norm(case['audio']))
        if case['id']=='inside_flat_box':assert frequency_error<=.01 and relative<=1e-6
        else:assert fit['at_bound'][2] and abs(parameters[m+2])>=2-1e-7
        assert truth_relative<=1e-10 and truth_spaces['base']['cost']<=1e-20
        rows.append(dict(id=case['id'],nominal_Hz=nominal.tolist(),original_fit=fit,
            true_frequency_Hz=case['frequency'].tolist(),true_chirp_Hz_per_s=case['chirp'].tolist(),
            waveform_relative_error=relative,max_frequency_error_Hz=frequency_error,
            observed_coordinate_subspaces=subspace,exact_coordinate_operator_contract=truth_spaces,
            exact_coordinate_wave_relative_error=truth_relative,
            amplitude_cost_reduction_percent=None if subspace['base']['cost']<=1e-20 else 100*(1-subspace['amplitude']['cost']/subspace['base']['cost']),
            quadrature_cost_reduction_percent=None if subspace['base']['cost']<=1e-20 else 100*(1-subspace['quadrature']['cost']/subspace['base']['cost']),
            relative_cost_defined=subspace['base']['cost']>1e-20))
        arrays[case['id']+'_audio']=case['audio'];arrays[case['id']+'_old']=old
        arrays[case['id']+'_quadrature']=waves['quadrature'];arrays[case['id']+'_exact']=truth_waves['base']
    np.savez_compressed(args.out/'known.npz',**arrays)
    report.update(result='known_smooth_chirp_flat_bound_clipping_observed_no_recording',cases=rows,arrays_sha256=sha(args.out/'known.npz'),
        limits=['No additional3Hz modulation exists in these known sources',
            'Exact coordinates only test a linear observation contract and never initialize the phase fit',
            'Clipping can be a cause in these fixtures; this does not identify its contribution in the real recording'])
    print(json.dumps(dict(result=report['result'],cases=[dict(id=r['id'],old_wave_error=r['waveform_relative_error'],
        bounds=r['original_fit']['at_bound'],A=r['amplitude_cost_reduction_percent'],Q=r['quadrature_cost_reduction_percent']) for r in rows])),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
