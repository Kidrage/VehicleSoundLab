"""Render the accepted DNA/LF pair through the shared C object/spatial adapter."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=8)
    args = parser.parse_args()
    if not .1 <= args.seconds <= 8:
        parser.error('seconds must be0.1..8; source comparison uses the frozen8s reference')
    workspace = args.workspace.resolve()
    repository = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(workspace / 'tools/python_deps'))
    from dna_scene_v1.render import make, sha
    from dna_scene_v1.validate import check
    from dna_scene_v1.review import make as review
    output = workspace / 'references/analysis/dna_scene_v1'
    output.mkdir(exist_ok=False)
    records = make(repository, output, args.probe.resolve(), args.seconds)
    checks = check(workspace, output, records, round(args.seconds * 48000))
    page = review(workspace, output)
    source_files = list((repository / 'modules/dna_scene').glob('*')) + list((repository / 'experiments/dna_scene_v1').glob('*'))
    source_files += list((repository / 'tools/dna_scene_v1').glob('*.py')) + [Path(__file__)]
    report = dict(schema='vsl.dna-scene-review/1', cases=records, checks=checks, page=str(page),
                  probe_sha256=sha(args.probe), source_sha256={str(p.relative_to(repository)): sha(p) for p in source_files if p.is_file()},
                  source_base_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repository, text=True).strip(),
                  source_has_uncommitted_changes=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=repository, text=True).strip()),
                  gain_policy='Fixed LF calibration1.6658265329883064 and output0.5; pair projection splits mono amplitude equally; no mix normalization, invented stereo or added brightening; review WAVs only have5ms endpoint fades',
                  seed_policy='Independent voice RNG state; explicit seed48271 for each retains accepted comparison. Hosts can supply separate seeds; no hidden global RNG',
                  status='Engineering source/spatial connection verified; spatial listening pending; wide RPM/load/driving integration incomplete')
    files = [dict(path=str(p.relative_to(output)), bytes=p.stat().st_size, sha256=sha(p)) for p in output.rglob('*') if p.is_file()]
    report['artifacts'] = files
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(page=str(page), checks=checks), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
