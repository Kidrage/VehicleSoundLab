"""Alternate old/new offline timings after actual-sample fidelity validation."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--old', type=Path, required=True)
parser.add_argument('--new', type=Path, required=True)
parser.add_argument('--fidelity', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


assert read(args.fidelity)['result'] == 'pass'
args.out.mkdir(parents=True, exist_ok=False)
(args.out/'bin').mkdir()
binaries = {}
for label, root in (('old', args.old), ('new', args.new)):
    report = read(root/'report.json')
    assert report['result'] == 'pass'
    source = root/'bin/VslAtlasPerf_probe.exe'
    assert sha(source) == report['probe_sha256']
    target = args.out/'bin'/(label+'.exe')
    shutil.copy2(source, target)
    binaries[label] = target
shutil.copy2(__file__, args.out/'executed_compare.py')
runs = []
for repeat in range(3):
    for context, bank in (('A', 0), ('E', 1)):
        labels = ('old', 'new') if repeat % 2 == 0 else ('new', 'old')
        pair = []
        for label in labels:
            trace = args.out/f'{context}_{repeat}_{label}.csv'
            command = [str(binaries[label]), str(bank), 'full', '240', '2', '1', '0', '16', 'shifts', str(trace)]
            result = subprocess.run(command, cwd=repo, check=True, capture_output=True, timeout=180)
            row = json.loads(result.stdout)
            row.update(label=label, case=context, repeat=repeat, command=command, trace_sha256=sha(trace))
            runs.append(row)
            with (args.out/'runs.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row)+'\n')
            with trace.open(newline='', encoding='utf-8') as stream:
                pair.append([(r['frame'],r['frames'],r['root_hz'],r['lower'],r['upper'],r['texture_updates'])
                             for r in csv.DictReader(stream)])
            print(json.dumps(dict(context=context, repeat=repeat, label=label, seconds=row['process_seconds'],
                p99_ms=row['p99_block_ms'], overruns=row['budget_exceedances'])), flush=True)
        assert pair[0] == pair[1], (context, repeat)
        assert all(r['shifts'] == 3 for r in runs[-2:])
comparisons = {}
for context in ('A', 'E'):
    groups = {label:[r for r in runs if r['case']==context and r['label']==label] for label in ('old','new')}
    medians = {label:{k:statistics.median(r[k] for r in values)
        for k in ('process_seconds','process_cycles','p99_block_ms','budget_exceedances')}
        for label,values in groups.items()}
    comparisons[context] = dict(medians=medians,
        process_seconds_reduction_percent=100*(1-medians['new']['process_seconds']/medians['old']['process_seconds']),
        process_cycles_reduction_percent=100*(1-medians['new']['process_cycles']/medians['old']['process_cycles']),
        matching_output_hash_pairs=sum(groups['old'][i]['output_hash']==groups['new'][i]['output_hash'] for i in range(3)),
        matching_source_hash_pairs=sum(groups['old'][i]['source_hash']==groups['new'][i]['source_hash'] for i in range(3)))
report = dict(schema='vsl.numeric-scope-paired/1', result='pass', comparisons=comparisons, runs=runs,
    fidelity_sha256=sha(args.fidelity), verifier_sha256=sha(__file__), control_traces_equal=True,
    baseline_reports_sha256={label:sha(root/'report.json') for label,root in (('old',args.old),('new',args.new))},
    scope='Three alternated normal-priority offline passages per context; no concurrent validation job; not device/hard-realtime qualification',
    numeric_note='flush_subnormals is the outer benchmark override; new runtime internally uses its scoped guard')
(args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(comparisons),flush=True)
