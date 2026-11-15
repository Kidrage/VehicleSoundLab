"""Read-only consumer of terminal mathematically audited fit captures.

Virtual64Hz-clock diagnostics and raw48k recording diagnostics remain separate.
This module neither starts fitting nor turns fitted trajectories into a voice.
"""
from pathlib import Path
import numpy as np
from research_archive_v1 import load,save,sha
from .measure import measure
from .compare import compare


def qualification(repo,study,audit):
    study,audit=Path(study),Path(audit)
    source,proof=load(study/'report.json'),load(audit/'report.json')
    if not (proof.get('result')=='independent_extraction_sound_composition_verified'
            and proof.get('operator_and_frozen_series_aggregation_qualified')
            and proof.get('producer_sha256')==sha(study/'report.json')
            and len(proof.get('cases',[]))==9):
        raise ValueError('Independent complete meter composition qualification required')
    for name,digest in source['sources'].items():
        if name.startswith('tools/extraction_sound_v1/'):
            if sha(Path(repo)/name)!=digest or sha(study/'exact_sources'/name)!=digest:
                raise ValueError('Qualified meter source version changed: '+name)
    # This flag is deliberately not claimed true: five tiny-line normalized
    # cross-FFT failures remain part of the qualified composition protocol.
    return dict(protocol=proof['result'],legacy_cross_operator_all_statistics_qualified=
        proof['legacy_cross_operator_all_statistics_qualified'],
        retained_legacy_normalized_failure_count=len(proof['legacy_normalized_failures']),
        study_sha256=sha(study/'report.json'),audit_sha256=sha(audit/'report.json'),
        sensitivity_is_certified=False)


def terminal(case,audit,*,repo,known=False):
    case,audit,repo=Path(case),Path(audit),Path(repo)
    info,proof=load(case/'report.json'),load(audit)
    kind=('independent_waveform_file_real_known_auditor_verified' if known
        else 'independent_waveform_file_real_verified')
    if proof.get('result')!=kind or not proof.get('verification_passed'):
        raise ValueError('Terminal independent mathematical verification required')
    row=next((c for c in proof['cases'] if c['label']==case.name),None)
    if row is None or not row.get('verification_passed'):
        raise ValueError('Case missing from independent mathematical verification')
    if row['producer_sha256']!=sha(case/'report.json'):
        raise ValueError('Case report differs from audited report')
    if row['capture_sha256']!=info['capture_sha256'] or sha(case/'capture.npz')!=row['capture_sha256']:
        raise ValueError('Capture differs from audited capture')
    for flag in ('solver_qualified','fidelity_qualified'):
        if row[flag]!=info[flag]:raise ValueError('Audit/producer qualification mismatch')
    binding=case.parent/('report.json' if known else 'run_spec.json')
    if proof['inputs'].get(str(binding))!=sha(binding):
        raise ValueError('Immutable source/spec binding differs from independent audit')
    if not known:
        spec=load(binding)
        if case.name not in spec['declared_cases'] or len(spec['declared_cases'])!=6 or not spec['only_one_sequential_run']:
            raise ValueError('Not one of the six declared real cases')
        for name,digest in spec['sources'].items():
            if sha(repo/name)!=digest or sha(case.parent/'exact_sources'/name)!=digest:
                raise ValueError('Bound real extraction source changed')
        for name,digest in spec['inputs'].items():
            if sha(name)!=digest:raise ValueError('Bound real extraction input changed')
        if sha(info['prepared_file'])!=info['prepared_sha256']:
            raise ValueError('Prepared source changed')
    with np.load(case/'capture.npz') as capture:z={name:capture[name] for name in capture.files}
    if not (np.array_equal(z['audio'][2048:-2048],z['target']) and z['wave'].shape==z['audio'].shape):
        raise ValueError('Original target or full-context geometry changed')
    if not known and not np.array_equal(z['orders'],np.arange(1,289)):
        raise ValueError('Original288orders required for real source diagnosis')
    return z,dict(label=case.name,known_control=known,
        case_report_sha256=sha(case/'report.json'),capture_sha256=sha(case/'capture.npz'),
        math_audit_sha256=sha(audit),binding_file=str(binding),binding_sha256=sha(binding),
        solver_qualified=info['solver_qualified'],fidelity_qualified=info['fidelity_qualified'],
        existing_weighted_metrics=info['metrics'])


def precision(measurement):
    result={}
    for prefix in ('broad','line'):
        if prefix+'_mean_power' not in measurement:continue
        result[prefix]={key:measurement[prefix+'_'+key].tolist() for key in (
            'power_defined','coherence_defined','power_resolved','coherence_resolved',
            'power_lower_margin','power_relative_uncertainty')}
    return result


def consume(case,audit,out,*,repo,meter_study,meter_audit,known=False):
    case,audit,out,repo=map(Path,(case,audit,out,repo))
    protocol=qualification(repo,meter_study,meter_audit)
    z,binding=terminal(case,audit,repo=repo,known=known)
    out.mkdir(parents=True,exist_ok=False)
    result=dict(result='running',source=binding,meter_protocol=protocol,regions=[],inputs={})
    for path in (case/'report.json',case/'capture.npz',audit,Path(meter_study)/'report.json',Path(meter_audit)/'report.json'):
        result['inputs'][str(path)]=sha(path)
    try:
        for name,part in (('original_target',slice(2048,-2048)),('complete_genuine_context',slice(None))):
            reference=measure(z['audio'][part],65536,orders=z['orders'],root=64)
            fitted=measure(z['wave'][part],65536,orders=z['orders'],root=64)
            output=out/(name+'.npz')
            np.savez_compressed(output,reference_audio=z['audio'][part],candidate_audio=z['wave'][part],
                **{'reference_'+k:v for k,v in reference.items()},**{'candidate_'+k:v for k,v in fitted.items()})
            result['regions'].append(dict(region=name,rate=65536,root=64,frames=len(z['audio'][part]),
                windows=len(reference['starts']),file=output.name,sha256=sha(output),
                signed_changes=compare(fitted,reference),reference_precision=precision(reference),
                candidate_precision=precision(fitted),
                clock_domain='virtual1024samples/cycle; not physicalHz or measuredRPM',
                fitted_timeline_is_diagnostic_only=True))
        if 'native' in z:
            native=measure(z['native'],48000)
            output=out/'raw_native48k.npz';np.savez_compressed(output,audio=z['native'],**native)
            result['native_recording']=dict(file=output.name,sha256=sha(output),frames=len(z['native']),rate=48000,
                windows=len(native['starts']),precision=precision(native),
                fitted_native_render_available=False,no_cross_clock_spectral_equality_claim=True)
        result.update(result='terminal_extraction_sound_diagnosed',no_gain_matching=True,
            independent_physical_source_separation=False,no_new_voice_or_C_or_hearing_promotion=True)
        save(out/'report.json',result)
        return result
    except BaseException as error:
        result.update(result='failed',error=repr(error));save(out/'report.json',result);raise
