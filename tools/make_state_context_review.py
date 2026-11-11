"""Bind visual witnesses, actual linked C state tables and frozen take traces."""
import csv
import json
import subprocess
from runtime_review import ROOT, sha
from reference_segments import CATALOG

OUT=ROOT/'references/analysis/state_context_v1'


def main():
    if (OUT/'verification.json').exists():
        raise SystemExit('Preserve completed state_context_v1 evidence.')
    frames=json.loads((OUT/'frames.json').read_text(encoding='utf-8'))
    notes=json.loads((OUT/'annotations.json').read_text(encoding='utf-8'))
    exe=ROOT/'build-experiment-state-context/Release/state_context_export.exe'
    native=json.loads(subprocess.check_output([str(exe)],text=True))
    native['binary_sha256']=sha(exe)
    native['linked_library_sha256']=sha(ROOT/'build-v016/Release/vsl_core.lib')
    (OUT/'runtime_tables.json').write_text(json.dumps(native,indent=2),encoding='utf-8')
    expected={'lifecycle':native['lifecycle'],'operating':[r['name'] for r in native['operating']],
        'fuel_mode':native['fuel_states'],'shift_stage':native['shift_stages']}
    traces={}
    # Audio-clock traces are model observations, never reference telemetry.
    for name in ['drive','neutral','lift']:
        path=ROOT/f'renders/v0.16.0/{name}_base.vsltake.csv'
        rows=list(csv.DictReader(path.open(newline='',encoding='utf-8')))
        records={}
        for field,legal in expected.items():
            seen={r[field] for r in rows};assert seen<=set(legal)
            records[field]=[value for value in legal if value in seen]
        traces[name]=dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path),rows=len(rows),
            observed_states=records,scope='Frozen native model take trace only. Sampling of state does not prove complete event coverage or reference identification.')
    (OUT/'native_trace_index.json').write_text(json.dumps(traces,indent=2),encoding='utf-8')
    links={}
    for row in notes['runtime_bindings'].values():
        for key,value in row.items():
            if value.startswith('src/'):
                links[value]=sha(ROOT/value)
    evidence=dict(schema='vsl.state-context-review/1',runtime=native['runtime'],
        upstream_revision='ac2b37d8639027d79934a2023cf8d1d37d3b2f96',
        catalog_sha256=sha(CATALOG),frame_index_sha256=sha(OUT/'frames.json'),
        annotations_sha256=sha(OUT/'annotations.json'),runtime_tables_sha256=sha(OUT/'runtime_tables.json'),
        native_trace_index_sha256=sha(OUT/'native_trace_index.json'),source_modules=links,
        conclusion=notes['conclusion'],scope='Evidence review only. No new audio interval, runtime voicing, state timing or subjective acceptance.')
    (OUT/'evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    # Embed review data so both localhost and file: work without fetch/CORS.
    data=dict(contexts=notes['contexts'],native=native,edits=notes['edits'])
    payload=json.dumps(data,ensure_ascii=False).replace('<','\\u003c')
    page=ROOT/'research/状态证据审阅V1.html'
    template=(ROOT/'tools/state_context_review.html').read_text(encoding='utf-8')
    page.write_text(template.replace('__REVIEW_DATA__',payload),encoding='utf-8')
    print(json.dumps(dict(result='built',frames=len(frames['frames']),contexts=len(notes['contexts']),
        edits=len(notes['edits']),operating_states=len(native['operating']),traces=traces),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
