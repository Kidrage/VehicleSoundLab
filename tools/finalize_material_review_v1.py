"""Bind terminal reference-rejection and startup-support evidence to final sources."""
import argparse
from pathlib import Path
import shutil
import urllib.request

from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output
    repo = Path(__file__).resolve().parents[1]
    analysis = Path('E:/VehicleSoundLab/references/analysis')
    material = analysis/'material_review_v1'
    support = analysis/'startup_source_support_v1'
    reports = [material/'verification1/report.json', material/'ui2/report.json',
        material/'web2/report.json', material/'web2/verification.json',
        *[support/name/'report.json' for name in ('diagnostic1', 'known1', 'fit1', 'audit1')]]
    assert all(load(path)['result'] == 'passed' for path in reports)
    clean = load(material/'verification1/report.json')
    assert clean['continuous_native_channels_exact'] == 19
    assert clean['historical_take_read_and_PCM_exact']
    assert not clean['persistent_service_restarted']
    for path, digest in clean['historical_files_unchanged'].items():
        assert sha(Path(path)) == digest
    assert load(material/'ui2/report.json')['UI']['own_window_closed']
    assert load(material/'web2/verification.json')['own_servers_closed']
    fit, audit = load(support/'fit1/report.json'), load(support/'audit1/report.json')
    assert fit['qualified_cases'] == audit['qualified_cases'] == []
    assert audit['reviewed_report_sha256'] == sha(support/'fit1/report.json')
    assert len(audit['waveforms']) == 32
    for path, digest in audit['waveforms'].items():
        assert sha(Path(path)) == digest
    for name in ('known1', 'fit1'):
        assert sha(repo/'tools/event_authoring/source_support.py') == sha(
            support/name/'exact_sources/tools/event_authoring/source_support.py')
    assert sha(repo/'tools/verify_material_review_web_v1.cjs') == sha(material/'web2/executed_browser.cjs')
    assert sha(repo/'tools/verify_material_review_web_v1.py') == sha(material/'web2/executed_verification.py')
    snapshot = material/'verification1/exact_sources'
    changed = [p.relative_to(snapshot).as_posix() for p in sorted(snapshot.rglob('*'))
               if p.is_file() and sha(p) != sha(repo/p.relative_to(snapshot))]
    assert changed == ['tools/vehicle_controller/events.py']
    # This final text change was exercised by the terminal ui2 owned-window test.
    runtime = load(analysis/'A_exterior_startup_v1/selection1/runtime.json')
    assert len(runtime) == 459 and all(sha(repo/name) == digest for name, digest in runtime.items())
    preset_path = material/'verification1/controller-preset.json'
    preset = load(preset_path)
    assert 'afterfire' not in preset['event_overrides']
    assert {'crank', 'catch'} <= preset['event_overrides'].keys()
    base = 'http://127.0.0.1:8789/references/analysis/material_review_v1/verification1/review/'
    http = []
    for path in sorted((material/'verification1/review').iterdir()):
        if not path.is_file():
            continue
        with urllib.request.urlopen(base+path.name, timeout=20) as response:
            data = response.read()
            assert response.status == 200 and data == path.read_bytes()
        http.append(dict(path=str(path), bytes=len(data), sha256=sha(path)))
    out.mkdir(parents=True, exist_ok=False)
    sources = [
        'AGENTS.md', 'research/material_review_decisions.json',
        'research/startup_source_support_v1_plan.json',
        'handoff/回火参考排除与演示修正V1.md', 'handoff/启动声源频带控制核查V1.md',
        'tools/event_authoring/material_reviews.py', 'tools/event_authoring/source_support.py',
        *['tools/vehicle_controller/'+name+'.py' for name in ('recipe', 'take', 'events', 'ui')],
        'tools/event_designer/workspace.py', 'tools/event_designer/package.py',
        'tools/sound_designer/web/events.js', 'tools/vehicle_scenarios/start_idle.py',
        'tools/vehicle_scenarios/web/app.js',
        *['tools/'+name for name in ('inspect_startup_source_support_v1.py',
            'verify_startup_source_support_v1.py', 'refine_startup_source_support_v1.py',
            'audit_startup_source_support_v1.py', 'audit_startup_contour_ensemble_v1.py',
            'verify_material_review_v1.py', 'verify_material_review_web_v1.py',
            'verify_material_review_web_v1.cjs', 'finalize_material_review_v1.py')]]
    final_sources = {}
    for name in sources:
        dest = out/'final_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dest)
        final_sources[name] = sha(dest)
        assert final_sources[name] == sha(repo/name)
    report_bindings = {str(path): sha(path) for path in reports}
    material_summary = dict(result='passed', user_decision='E reference unsuitable as afterfire',
        corrected_review_url=base+'index.html', corrected_preset=str(preset_path),
        corrected_preset_sha256=sha(preset_path), no_afterfire_in_corrected_demo=True,
        continuous_native_channels_exact=19, historical_replay_preserved=True,
        final_UI_and_browser_reports_bound=True, earlier_snapshot_changed_files=changed,
        changed_file_validation='ui2 final empty-bank text check',
        mobile_visual_limitation='web2 workbench screenshot has a transient toast overlay',
        published_files=http, final_sources=final_sources, terminal_reports=report_bindings,
        delivery_root=str(out), runtime_files_unchanged=459,
        persistent_service_restarted=False, goal_complete=False, timbre_accepted=False)
    support_summary = dict(result='passed', candidate_result='both_refused', qualified_cases=[],
        independent_saved_C_waveforms=32,
        independent_max_spectral_db_disagreement=audit['max_spectral_db_disagreement'],
        cases=[dict(kind=c['kind'], optimizer_terminated=c['fitting']['optimizer_terminated'],
                    relative_legacy_shape_improvement=c['fitting']['relative_legacy_shape_improvement'],
                    adopted=c['adopted']) for c in fit['cases']],
        final_sources=final_sources, terminal_reports=report_bindings, delivery_root=str(out),
        runtime_files_unchanged=459, no_candidate_promoted=True,
        goal_complete=False, timbre_accepted=False)
    save(repo/'research/material_review_v1_verification.json', material_summary)
    save(repo/'research/startup_source_support_v1_verification.json', support_summary)
    save(out/'material_verification.json', material_summary)
    save(out/'startup_verification.json', support_summary)
    entries = [dict(path=p.relative_to(out).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
               for p in sorted(out.rglob('*')) if p.is_file()]
    save(out/'manifest.json', dict(files=entries, file_count=len(entries),
                                  bytes=sum(row['bytes'] for row in entries)))
    print('final sources and terminal reports bound; published review exact; no candidate promoted', flush=True)


if __name__ == '__main__':
    main()
