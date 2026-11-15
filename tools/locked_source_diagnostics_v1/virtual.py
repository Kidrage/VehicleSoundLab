"""Same qualified full stereo meter, applied to the explicitly new source target."""
from pathlib import Path
import numpy as np
from research_archive_v1 import save, sha
from extraction_sound_v1.consume import qualification, precision
from extraction_sound_v1.measure import measure
from extraction_sound_v1.compare import compare
from .input import terminal


def consume(case, audit, out, *, repo, meter_study, meter_audit, known=False):
    out = Path(out)
    protocol = qualification(repo, meter_study, meter_audit)
    z, binding = terminal(case, audit, repo=repo, known=known)
    out.mkdir(parents=True, exist_ok=False)
    report = dict(result='running', source=binding, meter_protocol=protocol, regions=[], inputs=dict(binding['inputs']))
    for path in (Path(meter_study)/'report.json', Path(meter_audit)/'report.json'):
        report['inputs'][str(path)] = sha(path)
    try:
        for name, part in (('new_target', slice(2048, -2048)), ('complete_genuine_context', slice(None))):
            reference = measure(z['audio'][part], 65536, orders=z['orders'], root=64)
            candidate = measure(z['wave'][part], 65536, orders=z['orders'], root=64)
            output = out/(name+'.npz')
            np.savez_compressed(output, reference_audio=z['audio'][part], candidate_audio=z['wave'][part],
                **{'reference_'+key: value for key, value in reference.items()},
                **{'candidate_'+key: value for key, value in candidate.items()})
            report['regions'].append(dict(region=name, rate=65536, root=64, frames=len(z['audio'][part]),
                windows=len(reference['starts']), file=output.name, sha256=sha(output), signed_changes=compare(candidate, reference),
                reference_precision=precision(reference), candidate_precision=precision(candidate),
                clock_domain='virtual1024samples/cycle; not physicalHz or measuredRPM',
                explicit_legacy_calibration_is_not_audio_reference=True, fitted_timeline_is_diagnostic_only=True))
        if 'native' in z:
            native = measure(z['native'], 48000)
            output = out/'raw_native48k.npz'; np.savez_compressed(output, audio=z['native'], **native)
            report['native_recording'] = dict(file=output.name, sha256=sha(output), frames=len(z['native']), rate=48000,
                windows=len(native['starts']), precision=precision(native), fitted_native_render_available=False,
                no_cross_clock_spectral_equality_claim=True)
        report.update(result='locked_source_virtual_case_measured', no_gain_matching=True,
            independent_physical_source_separation=False, no_C_or_default_or_hearing_or_sustained_promotion=True)
        save(out/'report.json', report)
        return report
    except BaseException as error:
        report.update(result='failed', error=repr(error)); save(out/'report.json', report)
        raise
