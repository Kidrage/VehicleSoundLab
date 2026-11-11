"""Build a controlled LF phase comparison without changing accepted sources."""
import argparse
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--probe', type=Path, required=True)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    repository = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(workspace / 'tools/python_deps'))
    from coherent_low_v1.observation import observe, phase_evidence
    from coherent_low_v1.profiles import fit
    from coherent_low_v1.review import make, write_page
    from coherent_low_v1.plot import draw
    output = workspace / 'references/analysis/coherent_low_v1'
    output.mkdir(exist_ok=False)
    audio, provenance = observe(workspace)
    evidence = phase_evidence(audio)
    (output / 'phase-evidence.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    draw(output)
    models = fit(audio, output / 'models')
    renders = make(workspace, repository, output, args.probe.resolve(), audio)
    page = write_page(workspace, output)
    report = dict(schema='vsl.coherent-low-review/1', source=provenance, evidence=evidence,
                  models=models, renders=renders, page=str(page),
                  status='Controlled candidate pending listening; accepted Sound DNA and frozen driving DSP unchanged')
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(page=str(page), cycles=evidence['complete_cycles'],
                         stereo_difference_db=evidence['stereo_difference_relative_db'],
                         magnitude_control_error=models['phase_control_magnitude_max_error'],
                         accepted_DNA_equal=renders['accepted_DNA_float_equal']), ensure_ascii=True))


if __name__ == '__main__':
    main()
