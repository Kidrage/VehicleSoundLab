"""Trace the existing rows to their frozen overlapping analysis windows."""
import numpy as np
from research_archive_v1 import load,sha


def trace(workspace,repo,cases):
    root=workspace/'baselines/coefficient_geometry_v1'
    manifest=load(root/'manifest.json')
    entries={v['path']:v['sha256'] for v in manifest['files']}
    inputs={str(root/'manifest.json'):sha(root/'manifest.json')}
    def frozen(name):
        path=root/name;assert sha(path)==entries[name]
        inputs[str(path)]=entries[name];return path
    source=load(frozen('evidence/real1/report.json'))
    name='tools/sound_dna/windowed.py'
    original=frozen('source/'+name)
    assert sha(repo/name)==source['sources'][name]==sha(original)
    results=[]
    for case in cases:
        label=case['label']
        old=next(v for v in source['cases'] if v['label']==label)
        packet=frozen('evidence/real1/'+label+'/source.npz')
        moments=frozen('evidence/real1/'+label+'/full/moments.npz')
        training=workspace/'references/analysis/relative_phase_v1/real1'/label/'training.npz'
        inputs[str(training)]=sha(training)
        with np.load(packet) as f:positions=f['positions']; rebuilt_count=len(f['rebuilt'])
        with np.load(moments) as f:rows=f['rows']
        with np.load(training) as f:assert np.array_equal(rows,f['source_rows'])
        assert old['source_arrays_sha256']==sha(packet)
        size,hop=4096,256
        starts=np.arange(0,len(positions)-size+1,hop)
        assert len(starts)==len(rows) and rebuilt_count==len(positions)
        center=positions[starts+size//2]
        assert np.all(np.diff(positions)>0)
        spans=positions[starts+size-1]-positions[starts]
        results.append(dict(label=label,coefficient_rows=len(rows),virtual_samples=len(positions),
            analysis_window_samples=size,analysis_hop_samples=hop,window_overlap_fraction=1-hop/size,
            acoustic_cycles_per_window=4,acoustic_cycles_per_hop=.25,
            maximum_disjoint_analysis_windows=len(positions)//size,
            observed_center_step_seconds_min=float(np.diff(center).min()),
            observed_center_step_seconds_max=float(np.diff(center).max()),
            observed_window_support_seconds_min=float(spans.min()),
            observed_window_support_seconds_max=float(spans.max()),
            renderer_assumed_endpoint_step_seconds=1/(4*case['root_hz']),
            temporal_coupling_may_include_window_overlap_pitch_tracking_and_source_motion=True,
            disjoint_windows_not_claimed_statistically_independent=True))
    return dict(result='frozen_original_window_and_row_provenance_verified',
        inputs=inputs,source_window_code_sha256=sha(original),cases=results,
        no_new_extraction_or_rows_computed=True)
