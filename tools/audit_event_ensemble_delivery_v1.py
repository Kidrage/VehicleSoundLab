"""Independently check delta inventory, bound reports, retained refusal and readback."""
import argparse
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--freeze',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    manifest=load(args.freeze/'manifest.json');listed={r['path'] for r in manifest['files']}
    assert listed=={p.relative_to(args.freeze).as_posix() for p in args.freeze.rglob('*') if p.is_file() and p!=args.freeze/'manifest.json'}
    assert sha(Path(manifest['base_freeze'])/'manifest.json')==manifest['base_manifest_sha256']
    for row in manifest['files']:
        path=args.freeze/row['path'];assert path.resolve().is_relative_to(args.freeze.resolve())
        assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256'],row['path']
    milestone=load(args.freeze/'repo/research/event_ensemble_v1_verification.json');root=args.freeze/'evidence'
    assert not milestone['goal_complete'] and not milestone['physical_afterfire_confirmed'] and not milestone['new_timbre_accepted']
    assert len(milestone['runtime_files'])==459
    assert all(sha(args.freeze/'repo'/name)==value for name,value in milestone['source_files'].items())
    for key,row in milestone['checks'].items():
        relative=Path(row['path']).relative_to(Path('E:/VehicleSoundLab/references/analysis/event_ensemble_v1'))
        evidence=root/relative;assert sha(evidence)==row['sha256'] and load(evidence)['result']=='passed'
    assert load(root/'audit1/report.json')['result']=='failed'
    assert load(root/'audit1/diagnosis.json')['old_numbers_reproduced_exactly']
    assert load(root/'web1/report.json')['own_server_closed'] and load(root/'review-web2/report.json')['own_service_closed']
    assert load(root/'audit2/report.json')['all_48_C_waveforms_checked']
    fields=load(root/'header1/expected-fields.json');actual=list(map(float,(root/'header1/readback.txt').read_text().split()))
    assert len(fields)==186 and actual==list(fields.values())
    refusal=load(root/'author1/report.json')['refused_project'];project=refusal['project']
    p=load(root/'author1/projects'/project/'project.json')
    assert p['analysis']['status']=='analysis_only' and not p['analysis']['response_summary']['qualified']
    assert (root/'author1/projects'/project/p['analysis_run']/'refused-fit.json').is_file()
    assert not any(r['qualified'] for r in load(root/'B-long1/report.json')['cases'])
    report=dict(result='passed',files=len(listed),bytes=sum(r['bytes'] for r in manifest['files']),
        manifest_sha256=sha(args.freeze/'manifest.json'),all_sources_reports_and_readback_exact=True,
        rejected_profile_and_original_audit_failure_retained=True,physical_afterfire_confirmed=False,goal_complete=False)
    save(args.output/'report.json',report);print(report,flush=True)


if __name__=='__main__':main()
