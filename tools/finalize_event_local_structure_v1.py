"""Bind the executed local observer, independent audit and count-aware findings."""
import argparse
from pathlib import Path
import shutil

from research_archive_v1 import load,save,sha,verify


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    root=Path('E:/VehicleSoundLab/references/analysis/event_local_structure_v1')
    stages=['known1','source1','audit1','summary1','summary2']
    reports={name:load(root/name/'report.json') for name in stages}
    assert all(r['result']=='passed' for r in reports.values())
    known=reports['known1'];real=reports['source1'];audit=reports['audit1']
    assert len(known['observations'])==80 and audit['observations']==24 and len(real['cases'])==3
    assert real['known_first_sha256']==sha(root/'known1/report.json')
    assert audit['input_report_sha256']==sha(root/'source1/report.json')
    assert (root/'summary1/measurements.csv').read_bytes()==(root/'summary2/measurements.csv').read_bytes()
    assert reports['summary1']['displayed_primary']==reports['summary2']['displayed_primary']
    for name,digest in real['source_bindings'].items():
        assert sha(repo/name)==digest and sha(root/'source1/exact_sources'/name)==digest
    inputs={}
    for case in real['cases']:
        folder=root/'source1'/case['id']
        assert sha(folder/'source.wav')==case['source_wave_sha256']
        assert sha(case['source']['path'])==case['source']['sha256']
        inputs[str(folder/'source.wav')]=sha(folder/'source.wav')
        for row in case['observations']:
            assert sha(folder/(row['id']+'.json'))==row['sha256']
            assert sha(folder/(row['id']+'.npz'))==row['array_sha256']
            inputs[str(folder/(row['id']+'.json'))]=row['sha256']
            inputs[str(folder/(row['id']+'.npz'))]=row['array_sha256']
    runtime=load(root.parent/'A_exterior_startup_v1/selection1/runtime.json')
    assert len(runtime)==459 and all(sha(repo/name)==digest for name,digest in runtime.items())
    sources=set(real['source_bindings'])|{
        'AGENTS.md','handoff/启动局部频率与相位记忆V1.md',
        'research/event_local_structure_followup_v1_plan.json',
        'research/A_exterior_startup_v1_selection.json',
        'tools/summarize_event_local_structure_v1.py','tools/finalize_event_local_structure_v1.py',
        'tools/research_archive_v1.py','tools/event_authoring/audio.py'}
    bindings={}
    for name in sorted(sources):
        dest=out/'final_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest);bindings[name]=sha(dest)
        assert bindings[name]==sha(repo/name)
    figures=['source1/source-spectra.png','source1/phase-memory.png','source1/context.png','summary2/phase-memory-counted.png']
    summary=dict(result='passed',goal_complete=False,timbre_accepted=False,runtime_integrated=False,
        qualified_cases=[],known_observations=80,independently_audited_source_observations=24,
        maximum_independent_complex_coefficient_error_FS=max(r['maximum_complex_error_FS'] for r in audit['cases']),
        source_cases=[dict(id=c['id'],source=c['source']) for c in real['cases']],
        native_fullband_preserved=True,no_stereo_fold=True,no_source_fit_or_generator_promotion=True,
        phase_counts_and_sparse_long_windows_preserved=True,
        all_peak_widths_and_adjacent_graphs_independently_checked=True,
        final_sources=bindings,source_artifacts=inputs,
        terminal_reports={str(root/name/'report.json'):sha(root/name/'report.json') for name in stages},
        figures_viewed={str(root/name):sha(root/name) for name in figures},
        final_csv_sha256=sha(root/'summary2/measurements.csv'),summary1_retained_numeric_identity=True,
        runtime_voice_files_unchanged=459,delivery_root=str(out),
        limitation='Selected-peak finite observations do not identify physical oscillator/noise fractions or RPM. Overlap causes apparent memory; long-window ambiguity yields very small samples. New controllable source generation and human listening remain outstanding.')
    save(repo/'research/event_local_structure_v1_verification.json',summary)
    save(out/'verification.json',summary)
    entries=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
             for p in sorted(out.rglob('*')) if p.is_file()]
    save(out/'manifest.json',dict(files=entries,file_count=len(entries),bytes=sum(e['bytes'] for e in entries)))
    verify(out)
    print('known80/source24/independent audit and count-aware evidence bound; goal active',flush=True)


if __name__=='__main__':main()
