"""Freeze startup control fixes, original failures, exact sources and audio evidence."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from startup_response_evidence_v1 import sha, verify


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    data = Path('E:/VehicleSoundLab')
    evidence = data/'renders/startup_abort_v1'
    analysis = data/'references/analysis/startup_abort_v1'
    audit = read(evidence/'milestone-check1/report.json')
    assert audit['result'] == 'passed' and not audit['goal_complete']
    assert audit['verifier_sha256'] == sha(repo/'tools/verify_startup_abort_milestone_v1.py')
    for name in ('fixed3', 'regression3', 'ui3', 'stop-fixture2', 'cycle2'):
        verify(repo, read(evidence/name/'source_binding.json'))
    checks = {}
    for name, count in (('build2.log', 3), ('event-control-build2.log', 2)):
        content = (evidence/name).read_text(encoding='utf-8')
        assert '100% tests passed out of '+str(count) in content and '***Failed' not in content, name
        checks[name] = sha(evidence/name)
    assert '***Failed' in (evidence/'queue-regression1/test.log').read_text(encoding='utf-8')
    assert 'check_full_automatic_queue' in (evidence/'queue-regression1/control_checks.c').read_text()
    review = read(analysis/'review2/report.json')
    assert review['new']['bridge_sha256'] == audit['fixed']['bridge_sha256']
    assert sha(analysis/'review2/executed_build.py') == sha(repo/'tools/build_startup_abort_review_v1.py')
    for name, digest in review['files'].items():
        assert sha(analysis/'review2'/name) == digest, name
    for folder, verifier in (('web2', 'verify_startup_abort_web_v1.cjs'),
                             ('cycle-web2', 'verify_exhaust_cycle_web_v1.cjs')):
        report = read(evidence/folder/'report.json')
        assert sha(evidence/folder/'executed_verification.cjs') == report['verifier_sha256'] == sha(repo/'tools'/verifier)
    proofs = evidence/'final-test-build'
    proofs.mkdir(exist_ok=False)
    for name in ('experiments/event_synth_v1/control_checks.c', 'modules/event_control/policy.c',
                 'modules/event_control/api.h', 'modules/event_control/scheduler.c'):
        target = proofs/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, target)
    for path in (repo/'build-event-control-stop-v1/bin/Release').glob('*.exe'):
        shutil.copy2(path, proofs/path.name)
    document = repo/'handoff/启动中断与控制台V5.md'
    report = dict(audit, schema='vsl.startup-abort-milestone/1',
                  documentation_sha256=sha(document), finalizer_sha256=sha(__file__),
                  original_A_context='references/analysis/event_sources_v1/timelines5/A_startup',
                  source_tests=checks, source_tests_total=5,
                  review_url='http://127.0.0.1:8789/references/analysis/startup_abort_v1/review2/index.html',
                  cycle_url='http://127.0.0.1:8789/references/analysis/startup_abort_v1/cycle-review2/index.html',
                  archive=str(args.output), archive_independently_audited=False,
                  note='Independent manifest audit is a separate external report; do not rewrite this frozen file afterward.')
    (repo/'research/startup_abort_v1_verification.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    subprocess.run(['git', 'diff', '--check'], cwd=repo, check=True)
    args.output.mkdir(parents=True, exist_ok=False)
    subprocess.run(['git', 'diff', '--binary', '--output='+str(args.output/'working-tree.patch')], cwd=repo, check=True)
    names = set()
    for command in [('diff', '--name-only', '-z'), ('ls-files', '--others', '--exclude-standard', '-z')]:
        names.update(x for x in subprocess.check_output(['git', *command], cwd=repo).decode('utf-8').split('\0') if x)
    names.update(r['path'] for r in read(evidence/'fixed3/source_binding.json')['files'])
    for name in sorted(names):
        source = repo/name
        if source.is_file():
            target = args.output/'repo'/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    shutil.copytree(evidence, args.output/'evidence', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(analysis, args.output/'analysis')
    shutil.copytree(data/'references/analysis/event_sources_v1/timelines5/A_startup', args.output/'original-context/A_startup')
    for name, row in audit['binaries'].items():
        binary = Path(row['path'])
        assert sha(binary) == row['sha256']
        target = args.output/'binaries'/name/binary.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(binary, target)
    shutil.copy2(data/'renders/event_system_v1/launch1/approval-rejections.json', args.output/'prior-launch-rejections.json')
    manifest = dict(schema='vsl.startup-abort-delivery/1', created=datetime.now(timezone.utc).isoformat(),
                    base_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
                    goal_complete=False, timbre_accepted=False,
                    files=[dict(path=p.relative_to(args.output).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
                           for p in sorted(args.output.rglob('*')) if p.is_file()])
    (args.output/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    for row in manifest['files']:
        path = args.output/row['path']
        assert path.stat().st_size == row['bytes'] and sha(path) == row['sha256']
    print(json.dumps(dict(output=str(args.output), files=len(manifest['files']),
                         bytes=sum(row['bytes'] for row in manifest['files']), goal_complete=False)))


if __name__ == '__main__':
    main()
