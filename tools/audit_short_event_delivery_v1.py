"""Independent archive inventory and actual-source boundary audit."""
import argparse
from pathlib import Path
from research_archive_v1 import load,save,sha


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--freeze',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    manifest=load(args.freeze/'manifest.json');listed={row['path'] for row in manifest['files']}
    assert listed=={p.relative_to(args.freeze).as_posix() for p in args.freeze.rglob('*') if p.is_file() and p!=args.freeze/'manifest.json'}
    assert sha(Path(manifest['base_freeze'])/'manifest.json')==manifest['base_manifest_sha256']
    for row in manifest['files']:
        path=args.freeze/row['path'];assert path.resolve().is_relative_to(args.freeze.resolve())
        assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256'],row['path']
    milestone=load(args.freeze/'repo/research/short_event_authoring_v1_verification.json')
    assert not milestone['goal_complete'] and milestone['runtime_voice_files_unchanged']==459
    assert all(sha(args.freeze/'repo'/name)==digest for name,digest in milestone['source_files'].items())
    for key,row in milestone['checks'].items():
        original=Path(row['path']);relative=original.relative_to(Path('E:/VehicleSoundLab/references/analysis/short_event_scan_v1'))
        evidence=args.freeze/'evidence'/relative
        assert sha(evidence)==row['sha256'] and load(evidence)['result']=='passed'
    fits=load(args.freeze/'evidence/B-fits2/report.json')
    assert len(fits['selection'])==6 and sum('C_seeds' in row for row in fits['selection'])==2
    assert not any(row.get('multi_seed_qualified') for row in fits['selection'])
    assert not fits['global_event_bank_changed'] and not fits['physical_afterfire_confirmed']
    assert load(args.freeze/'evidence/source-power-audit.json')['all_windows']==1002
    assert load(args.freeze/'evidence/web6/report.json')['own_server_closed']
    assert load(args.freeze/'evidence/review-web1/report.json')['own_service_closed']
    report=dict(result='passed',files=len(listed),bytes=sum(row['bytes'] for row in manifest['files']),
        manifest_sha256=sha(args.freeze/'manifest.json'),source_files_and_checks_exact=True,
        failed_candidate_fits_retained=True,physical_afterfire_confirmed=False,goal_complete=False)
    save(args.output/'report.json',report);print(report,flush=True)
