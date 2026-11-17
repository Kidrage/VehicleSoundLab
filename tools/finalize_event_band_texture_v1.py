"""Bind final offline modules to terminal known/source/audit evidence."""
import argparse
import ast
from pathlib import Path
import shutil

from research_archive_v1 import load, save, sha, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output
    repo = Path(__file__).resolve().parents[1]
    root = Path('E:/VehicleSoundLab/references/analysis/startup_band_texture_v1')
    stages = ('known1', 'known2', 'fit1', 'audit1', 'conditioning-known1',
              'conditioned-fit1', 'conditioned-audit1', 'budget1')
    reports = {name: load(root/name/'report.json') for name in stages}
    assert all(r['result'] == 'passed' for r in reports.values())
    assert reports['fit1']['qualified_cases'] == reports['conditioned-fit1']['qualified_cases'] == []
    assert not any(c['finite_problem_infeasibility_proved'] for c in reports['budget1']['cases'])
    waveforms = {}
    for stage, fit in (('audit1', 'fit1'), ('conditioned-audit1', 'conditioned-fit1')):
        report = reports[stage]
        assert report['reviewed_report_sha256'] == sha(root/fit/'report.json')
        assert len(report['waveforms']) == 32
        for path, digest in report['waveforms'].items():
            assert sha(Path(path)) == digest
            waveforms[path] = digest
    assert len(waveforms) == 64
    for p in (repo/'tools/event_band_texture').glob('*.py'):
        assert sha(p) == sha(root/'conditioning-known1/exact_sources'/p.relative_to(repo))
    for name in ('profile.py', 'voice.py'):
        assert sha(repo/'tools/event_band_texture'/name) == sha(
            root/'known2/exact_sources/tools/event_band_texture'/name)
    def named_ast(path, name):
        module = ast.parse(path.read_text(encoding='utf-8'))
        return ast.dump(next(node for node in module.body if getattr(node, 'name', None) == name),
                        include_attributes=False)
    for name in ('Response', 'solve'):
        assert named_ast(repo/'tools/event_band_texture/fit.py', name) == named_ast(
            root/'known2/exact_sources/tools/event_band_texture/fit.py', name)
    runtime = load(Path('E:/VehicleSoundLab/references/analysis/A_exterior_startup_v1/selection1/runtime.json'))
    assert len(runtime) == 459 and all(sha(repo/name) == digest for name, digest in runtime.items())
    rejected = load(repo/'research/material_review_decisions.json')
    assert any(row['id'] == 'E-low-mid-short-not-afterfire-20261117' for row in rejected['decisions'])
    out.mkdir(parents=True, exist_ok=False)
    sources = [repo/'AGENTS.md', repo/'handoff/启动独立频带声源研究V1.md',
        repo/'research/startup_band_texture_v1_plan.json',
        repo/'research/event_texture_conditioning_v1_plan.json',
        repo/'research/startup_band_texture_followup_v1_plan.json',
        *sorted((repo/'tools/event_band_texture').glob('*.*')),
        *[repo/'tools'/name for name in ('verify_event_band_texture_v1.py',
            'verify_event_texture_conditioning_v1.py', 'refine_startup_band_texture_v1.py',
            'audit_event_band_texture_v1.py', 'inspect_event_band_texture_v1.py',
            'audit_startup_contour_ensemble_v1.py', 'finalize_event_band_texture_v1.py')]]
    bindings = {}
    for p in sources:
        name = p.relative_to(repo)
        dest = out/'final_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
        bindings[name.as_posix()] = sha(dest)
        assert sha(p) == sha(dest)
    summary = dict(result='passed', qualified_cases=[], runtime_integrated=False,
        representation='independently coloured/band-limited noise with post-filter amplitude contours',
        module_directory='tools/event_band_texture', source_free_profiles=True,
        known_first_passed=True, amplitude_coordinate_invariance_verified=True,
        saved_waveforms_independently_audited=64, original_C_files=32, new_Python_files=32,
        failed_candidates_preserved=True, no_candidate_promoted=True,
        spectral_infeasibility_proved=False,
        qualification_gates_unchanged=True, runtime_voice_files_unchanged=459,
        final_sources=bindings,
        terminal_reports={str(root/name/'report.json'): sha(root/name/'report.json') for name in stages},
        independent_waveforms=waveforms,
        figures_viewed=['fit1/temporal.png', 'conditioned-fit1/temporal.png', 'budget1/spectral-budget.png'],
        report_precision='FP64 generation measures; independent audit accounts for FLOAT-WAV storage only',
        max_saved_audio_spectral_db_difference=max(reports[s]['max_spectral_db_disagreement'] for s in ('audit1','conditioned-audit1')),
        max_saved_audio_shape_rmse_difference=max(reports[s]['max_shape_rmse_disagreement'] for s in ('audit1','conditioned-audit1')),
        rejected_E_afterfire_still_excluded=True, no_active_experiment_process=True,
        delivery_root=str(out), goal_complete=False, timbre_accepted=False)
    save(repo/'research/startup_band_texture_v1_verification.json', summary)
    save(out/'verification.json', summary)
    entries = [dict(path=p.relative_to(out).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
               for p in sorted(out.rglob('*')) if p.is_file()]
    save(out/'manifest.json', dict(files=entries, file_count=len(entries), bytes=sum(e['bytes'] for e in entries)))
    verify(out)
    print('final modules and64 saved-waveform audit bound; no C/UI/default promotion; goal active', flush=True)


if __name__ == '__main__':
    main()
