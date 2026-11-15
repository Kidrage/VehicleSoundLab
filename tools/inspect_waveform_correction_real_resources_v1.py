"""Conditional SAMEsix genuine-context resources after the full native audit."""
import argparse
import shutil
from pathlib import Path
from research_archive_v1 import load,save,sha
from run_waveform_stream_full_v1 import physical_memory


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','full-audit','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_inspection.py')
    audit=load(a.full_audit/'report.json')
    assert audit['result']=='independent_waveform_correction_native_full_verified'
    assert audit['solver_qualified'] and audit['fidelity_qualified'] and audit['all_phase_releases_verified']
    root=a.workspace/'baselines/waveform_banded_v1'
    assert sha(root/'manifest.json')==load(repo/'research/waveform_banded_v1_summary.json')['manifest_sha256']
    path=root/'evidence/native_context1/report.json'
    entries={v['path']:v['sha256'] for v in load(root/'manifest.json')['files']}
    assert sha(path)==entries['evidence/native_context1/report.json']
    context=load(path);memory=physical_memory();free=min(memory['available_physical_bytes'],memory['available_commit_bytes'])
    r=dict(result='waveform_correction_real_resources_inspected',cases=[],available_memory=memory,
        inputs={str(p):sha(p) for p in (a.full_audit/'report.json',root/'manifest.json',path)},
        no_real_arrays_or_fit_allocated=True,outer_corrected_phase_qualified=False)
    for c in context['cases']:
        for label,N,M in (('original',c['frames'],c['nodes']),('genuine_context',c['frames']+4096,c['nodes']+16)):
            n=2*M*288;k=min(N,n)
            W,X,graph,T=8*4096*N,8*N*n,8*(k+n)*k,8*k*k
            right,inner=8*n*k,16*k*k
            base=W+X+graph+T;correction=X+right+inner
            current=max(base,correction)
            proposal=max(base-T,X+right,right+inner)
            def measure(main):
                required=main+3*1024**3//2+3*1024**3
                return dict(main_arrays_only=main,required_available=required,available_gate_passed=free>=required)
            r['cases'].append(dict(label=c['label'],scope=label,frames=N,nodes=M,orders=288,RHS=2,
                individual_bytes=dict(W_band=W,X=X,graph=graph,graph_T=T,inverse_right=right,inverse_inner=inner),
                current_qualified_pipeline=measure(current),
                hypothetical_no_base_T_and_early_X_release=measure(proposal),
                hypothetical_path_implemented=False,conditional_NOT_peak_prediction=True))
    assert len(r['cases'])==12
    r['auditor_sha256']=sha(__file__);save(a.out/'report.json',r)
    for c in r['cases']:
        print(c['label'],c['scope'],c['current_qualified_pipeline'],
              'hypothetical',c['hypothetical_no_base_T_and_early_X_release'],flush=True)


if __name__=='__main__':main()
