"""Alternate frozen old/new binaries and require identical rendered hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--old', type=Path, required=True, help='Old run directory containing report.json and bin/')
parser.add_argument('--new', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


args.out.mkdir(parents=True, exist_ok=False)
(args.out/'bin').mkdir()
reports, binaries = {}, {}
for label, root in (('old', args.old), ('new', args.new)):
    reports[label] = json.loads((root/'report.json').read_text(encoding='utf-8'))
    assert reports[label]['result'] == 'pass'
    source = root/'bin/VslAtlasPerf_probe.exe'
    assert sha(source) == reports[label]['probe_sha256']
    target = args.out/'bin'/(label+'.exe');shutil.copy2(source, target);binaries[label] = target
shutil.copy2(__file__, args.out/'executed_compare.py')
cases = [('A', 0), ('E', 1)]
runs = []
for repeat in range(3):
    for name, bank in cases:
        order = ('old', 'new') if repeat % 2 == 0 else ('new', 'old')
        for label in order:
            trace = args.out/f'{name}_{repeat}_{label}.csv'
            command = [str(binaries[label]), str(bank), 'full', '240', '2', '1', '0', '16', 'shifts', str(trace)]
            result = subprocess.run(command, cwd=repo, check=True, capture_output=True, timeout=180)
            row = json.loads(result.stdout)
            row.update(label=label, case=name, repeat=repeat, command=command, trace_sha256=sha(trace))
            runs.append(row)
            with (args.out/'runs.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row)+'\n')
            print(json.dumps(dict(case=name, label=label, repeat=repeat, seconds=row['process_seconds'],
                                  p99_ms=row['p99_block_ms'], overruns=row['budget_exceedances'])), flush=True)
        pair = [r for r in runs if r['case'] == name and r['repeat'] == repeat]
        assert pair[0]['output_hash'] == pair[1]['output_hash']
        assert pair[0]['source_hash'] == pair[1]['source_hash']
        assert pair[0]['shifts'] == pair[1]['shifts'] == 3
summary = {}
for name, _ in cases:
    group = {label: [r for r in runs if r['case'] == name and r['label'] == label] for label in ('old', 'new')}
    medians = {label: {key: statistics.median(r[key] for r in rows)
                      for key in ('process_seconds', 'p99_block_ms', 'budget_exceedances', 'process_cycles')}
               for label, rows in group.items()}
    summary[name] = dict(medians=medians, process_seconds_reduction_percent=100*(1-medians['new']['process_seconds']/medians['old']['process_seconds']),
                         process_cycles_reduction_percent=100*(1-medians['new']['process_cycles']/medians['old']['process_cycles']))
result = dict(schema='vsl.atlas-performance-paired/1', result='pass', comparisons=summary, runs=runs,
              reference_reports_sha256={label: sha(root/'report.json') for label, root in (('old', args.old), ('new', args.new))},
              source_sha256=sha(Path(__file__)), all_output_and_source_hashes_exact=True,
              scope='Three alternated offline passages per binary/context; no device or hard-realtime claim')
(args.out/'report.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
print(json.dumps(summary), flush=True)
