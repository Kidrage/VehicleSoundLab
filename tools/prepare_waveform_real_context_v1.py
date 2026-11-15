"""Inspect six frozen real observations and resources; no fit or fake context."""
import argparse
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','known-audit','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from run_waveform_stream_full_v1 import physical_memory
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    audit=load(a.known_audit/'report.json');assert audit['solver_qualified'] and audit['fidelity_qualified']
    parent=a.workspace/'baselines/observer_frequency_v1'
    manifest=load(parent/'manifest.json');entries={v['path']:v['sha256'] for v in manifest['files']}
    assert sha(parent/'manifest.json')==load(repo/'research/observer_frequency_v1_summary.json')['manifest_sha256']
    def frozen(name):
        path=parent/name;assert sha(path)==entries[name];return path
    report_path=frozen('evidence/real1/report.json');old=load(report_path);assert len(old['cases'])==6
    r=dict(result='running',cases=[],inputs={str(p):sha(p) for p in (parent/'manifest.json',report_path,a.known_audit/'report.json')},
        sources={},available_memory=physical_memory(),no_fit_or_resampling=True)
    for name in ('tools/prepare_waveform_real_context_v1.py','tools/run_waveform_stream_full_v1.py'):
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
    def shape(N,M):
        n=2*M*288;k=min(N,n)
        sizes=dict(W=8*N*N,X_raw=8*N*n,graph_raw=8*(k+n)*k,graph_R=8*k*k)
        total=sum(sizes.values());minimum=total+3*1024**3//2+3*1024**3
        return dict(frames=N,nodes=M,orders=288,independent_RHS=2,individual_array_bytes=sizes,
            coexisting_four_array_bytes=total,preflight_required_available=minimum,
            current_headroom_passed=min(r['available_memory']['available_physical_bytes'],r['available_memory']['available_commit_bytes'])>=minimum,
            conditional_only_NOT_allocated=True)
    for case in old['cases']:
        source=frozen('evidence/real1/'+case['label']+'/source.npz')
        scales=frozen('evidence/real1/'+case['label']+'/scale.npz')
        assert sha(source)==case['source_sha256'] and sha(scales)==case['scale_sha256']
        r['inputs'].update({str(p):sha(p) for p in (source,scales)})
        with np.load(source) as z,np.load(scales) as s:
            audio,native,coords,positions=z['audio'],z['native'],z['coordinates'],z['positions']
            assert audio.ndim==native.ndim==2 and audio.shape[1]==native.shape[1]==2
            assert len(coords)==len(audio) and np.all(np.diff(coords)>0)
            assert np.isfinite(audio).all() and np.isfinite(native).all() and np.isfinite(coords).all()
            assert s['scale'].shape==(288,1) and np.all(s['scale']>0)
            assert positions[0]==0 and positions[-1]==len(audio)-1 and np.all(np.diff(positions)>0)
            r['cases'].append(dict(label=case['label'],root_hz=case['root_hz'],original_frames=len(audio),
                original_nodes=len(positions),native_frames=len(native),source_rows=len(z['coefficients']),
                coordinate_first=float(coords[0]),coordinate_last=float(coords[-1]),
                min_coordinate_step=float(np.diff(coords).min()),max_coordinate_step=float(np.diff(coords).max()),
                native_coordinate_unit_and_outer_phase_NOT_requalified=True,
                original_target_only=shape(len(audio),len(positions)),
                proposed_2048_each_side=shape(len(audio)+4096,len(positions)+16),
                added_context_NOT_generated_or_assumed_available=True))
    r.update(result='waveform_real_six_context_resources_inspected',same6_original_arrays_and_scales=True,
        original_targets_fit_headroom_now=all(c['original_target_only']['current_headroom_passed'] for c in r['cases']),
        extended_targets_fit_headroom_now=all(c['proposed_2048_each_side']['current_headroom_passed'] for c in r['cases']),
        real6_fit_or_new_context_or_independent_phase_qualified=False,auditor_sha256=sha(__file__))
    save(a.out/'report.json',r)
    print(r['result'],'headroom original',r['original_targets_fit_headroom_now'],'extended',r['extended_targets_fit_headroom_now'],flush=True)
    for c in r['cases']:print(c['label'],c['original_frames'],c['original_nodes'],c['original_target_only']['coexisting_four_array_bytes'],c['proposed_2048_each_side']['coexisting_four_array_bytes'],flush=True)


if __name__=='__main__':main()
