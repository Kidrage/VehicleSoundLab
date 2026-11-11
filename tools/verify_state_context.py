"""Verify and freeze the read-only video/state evidence review."""
import csv
import json
import math
import re
import shutil
from fractions import Fraction
from runtime_review import ROOT, sha
from reference_segments import checked_source, catalog, CATALOG

OUT=ROOT/'references/analysis/state_context_v1'
SNAP=ROOT/'baselines/state_context_v1'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    if SNAP.exists() or (OUT/'verification.json').exists():
        raise SystemExit('Preserve completed state_context_v1 evidence.')
    index=read(OUT/'frames.json');notes=read(OUT/'annotations.json')
    tables=read(OUT/'runtime_tables.json');evidence=read(OUT/'evidence.json')
    assert len(index['frames'])==116 and len(index['sheets'])==9
    assert index['script_sha256']==sha(ROOT/'tools/video_state_frames.py')
    assert index['catalog_sha256']==sha(CATALOG)==evidence['catalog_sha256']
    media={key:checked_source(key) for key in ['A','B']}
    assert sha(ROOT/index['video'])==index['video_sha256']==media['A']['video_sha256']
    assert index['stream']['time_base']=='1/11988'
    time_base=Fraction(index['stream']['time_base']);by_name={}
    for row in index['frames']:
        assert row['file'] not in by_name
        by_name[row['file']]=row
        assert sha(OUT/row['file'])==row['sha256']
        assert float(row['pts']*time_base)==row['source_pts_seconds']
        interval=index['detail_window'] if row['window']=='rev_edit_detail' else index['windows'][row['window']]
        assert interval[0]<=row['source_pts_seconds']<=interval[1]
    for prefix,log,expected in [('frame_','frame_log.txt',94),('rev_edge_','rev_edge_log.txt',22)]:
        decoded=re.findall(r'\bn:\s*(\d+) pts:\s*(\d+) pts_time:([\d.]+)',(OUT/log).read_text(encoding='utf-8',errors='replace'))
        assert len(decoded)==expected
        for number,pts,_ in decoded:
            assert by_name[f'{prefix}{int(number)+1:03d}.jpg']['pts']==int(pts)
    for sheet in index['sheets']:
        assert sha(OUT/sheet['file'])==sheet['sha256']
        assert all(name in by_name for name in sheet['frames'])
    for edit in notes['edits']:
        assert all(name in by_name for name in edit['witnesses'])
    for context in notes['contexts']:
        assert all(name in by_name for name in context['new_frames'])
        assert all((ROOT/name).is_file() for name in context['images'])
        if context['segment_id']:
            segment=catalog()['segments'][context['segment_id']]
            assert context['seconds']==segment['seconds'] and segment['source']=='A'
    # Verify the final video frame in the catalogue interval; do not infer
    # an audio edit endpoint or an independently measured A/V offset.
    last=by_name['rev_edge_007.jpg']
    assert last['source_pts_seconds']<248
    assert float((last['pts']+400)*time_base)>=248
    assert tables['runtime']=='0.16.0' and tables['shared_five_templates']
    assert [len(tables[key]) for key in ['layers','operating','lifecycle','fuel_states','shift_stages']]==[6,8,6,5,4]
    assert all(len(row['level'])==6 and all(math.isfinite(x) for x in row['level']) for row in tables['operating'])
    assert tables['binary_sha256']==sha(ROOT/'build-experiment-state-context/Release/state_context_export.exe')
    assert tables['linked_library_sha256']==sha(ROOT/'build-v016/Release/vsl_core.lib')
    assert tables['linked_library_sha256']==sha(ROOT/'baselines/exhaust_envelope_v1/build-v016/Release/vsl_core.lib')
    for key,file in [('frame_index_sha256','frames.json'),('annotations_sha256','annotations.json'),
        ('runtime_tables_sha256','runtime_tables.json'),('native_trace_index_sha256','native_trace_index.json')]:
        assert evidence[key]==sha(OUT/file)
    for name,digest in evidence['source_modules'].items():
        assert sha(ROOT/name)==digest
    trace_index=read(OUT/'native_trace_index.json');observed={key:set() for key in ['operating','fuel_mode','shift_stage']}
    for record in trace_index.values():
        path=ROOT/record['path'];assert sha(path)==record['sha256']
        rows=list(csv.DictReader(path.open(newline='',encoding='utf-8')))
        assert len(rows)==record['rows']
        for key,values in record['observed_states'].items():
            assert {row[key] for row in rows}==set(values)
            if key in observed:observed[key].update(values)
    assert observed['operating']=={row['name'] for row in tables['operating']}
    assert observed['fuel_mode']==set(tables['fuel_states'])
    assert observed['shift_stage']==set(tables['shift_stages'])
    native=read(ROOT/'renders/v0.16.0/verification.json')
    for name,digest in native['binaries'].items():
        assert sha(ROOT/'build-v016/Release'/name)==digest
    source_count=0
    for item in read(ROOT/'baselines/v0.16.0/manifest.json')['files']:
        name=item['path']
        if name.startswith(('src/','tests/')) or name in ['CMakeLists.txt','Launch.cmd','Launch-character.cmd','build.ps1','AGENTS.md']:
            assert sha(ROOT/name)==item['sha256'],name
            source_count+=1
    assert source_count==144
    browser=read(OUT/'browser_qa.json')
    assert browser['result']=='pass' and browser['contexts']==6 and browser['image_metadata_loads']==8
    for key in ['all_eight_C_coefficient_rows_match','actual_muted_video_playback','context_switch_pauses_and_seeks','segment_end_stops_playback']:
        assert browser[key],key
    assert not browser['mobile_horizontal_overflow'] and not browser['javascript_errors']
    history={p.parent.name:sha(p) for p in sorted((ROOT/'baselines').glob('*/manifest.json'))}
    assert len(history)==23
    paths=['tools/video_state_frames.py','tools/make_state_context_review.py','tools/state_context_review.html',
        'tools/verify_state_context_ui.cjs','tools/verify_state_context.py',
        'tools/runtime_review.py','tools/reference_segments.py','references/segments_v1.json',
        'experiments/state_context_v1/export.c','experiments/state_context_v1/CMakeLists.txt',
        'build-experiment-state-context/Release/state_context_export.exe','build-v016/Release/vsl_core.lib',
        'research/状态证据审阅V1.html','research/状态证据与当前控制链V1.md',
        'research/goal_progress_state_context_v1.json','README.md',
        'references/analysis/lifecycle_v1/lifecycle_contact.jpg','references/analysis/lifecycle_v1/observations.json']
    paths+=list(evidence['source_modules'])
    report=dict(result='pass',study='state_context_v1',runtime='0.16.0 unchanged',
        exact_pts_frames=116,visual_contexts=6,visual_edit_observations=6,
        native_source_and_contract_files_unchanged=source_count,native_binaries_unchanged=native['binaries'],
        approved_media=media,catalog_sha256=sha(CATALOG),
        actual_C_table_sha256=sha(OUT/'runtime_tables.json'),native_trace_union={k:sorted(v) for k,v in observed.items()},
        browser_qa_sha256=sha(OUT/'browser_qa.json'),
        previous_snapshot_manifest_hashes=history,
        source_files={name:sha(ROOT/name) for name in paths},
        artifacts={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file()},
        scope='Read-only evidence/UI/profile export. No source audio processing, new native parameters, telemetry fit or subjective acceptance. Prior snapshot directories were not edited; their manifest identities are recorded, not a new audit of all their file contents.')
    (OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    paths += [p.relative_to(ROOT).as_posix() for p in OUT.iterdir() if p.is_file()]
    SNAP.mkdir()
    for name in sorted(set(paths)):
        target=SNAP/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    files=[dict(path=p.relative_to(SNAP).as_posix(),sha256=sha(p)) for p in sorted(SNAP.rglob('*')) if p.is_file()]
    manifest=dict(study='state_context_v1',base_runtime='0.16.0 unchanged',files=files,
        native_snapshot_manifest_sha256=sha(ROOT/'baselines/v0.16.0/manifest.json'),
        storage='Review sources, profile exporter, linked library, video frames and evidence included. Approved raw video/audio and float masters stay at their original hash-bound local paths.',
        status='Frozen visual context/control evidence review; no new real-vehicle telemetry or voicing acceptance.')
    (SNAP/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    assert all(sha(SNAP/item['path'])==item['sha256'] for item in files)
    print(json.dumps(dict(result='pass',snapshot_files=len(files),previous_manifests=len(history),
        native_files_unchanged=source_count,frames=len(index['frames']),contexts=len(notes['contexts'])),indent=2))


if __name__=='__main__':
    main()
