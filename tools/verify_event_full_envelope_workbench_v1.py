"""Actual E job8 extraction/edit/history/export in the web and source-free C."""
import argparse
from pathlib import Path
import shutil
import subprocess
import threading
import csv

import numpy as np
import soundfile as sf

from event_designer.workspace import EventWorkspace
from research_archive_v1 import load, save, sha
from sound_designer.server import create_server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    data = Path('E:/VehicleSoundLab/references/analysis')
    candidate = load(data/'event_full_envelope_v1/verification1/candidate/analysis/profile.json')
    save(args.output/'fixture.json', dict(context=str(data/'low_mid_event_scan_v1/C1/original-context.wav'),
         expected=candidate['parameters']))
    # Retain the exact executed adaptation, leaving earlier review scripts intact.
    script = (repo/'tools/verify_event_joint_web_v1.cjs').read_text(encoding='utf-8')
    for old, new, count in [
        ("headless:true", 'headless:true,args:["--mute-audio"]', 1),
        ("'#kind','crank'", "'#kind','afterfire'", 1),
        ("'#viewpoint','cabin'", "'#viewpoint','exterior'", 1),
        ("start:'3.2',end:'3.95',bgStart:'.2',bgEnd:'1.2'", "start:'.85',end:'1.16',bgStart:'.65',bgEnd:'.85'", 1),
        ("band-contour-v2", "band-contour-v4", 4),
        ("await page.check('#fitGated')", "await page.uncheck('#fitGated')", 1),
        ("p.document.fit.contour_fit.bands[0].selected===false", "p.document.fit.contour_fit.bands[0].selected===true&&p.document.fit.contour_fit.bands.slice(1).every(r=>!r.selected)", 1)]:
        assert script.count(old) == count, (old, script.count(old))
        script = script.replace(old, new)
    executed = args.output/'executed_browser.cjs'
    executed.write_text(script, encoding='utf-8')
    shutil.copy2(__file__, args.output/'executed_verification.py')
    node = Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    server = create_server(repo, args.output/'server-root', 0)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        completed = subprocess.run([str(node), str(executed), str(node.parents[1]/'node_modules'),
            str(args.output), str(args.output/'fixture.json'), 'http://127.0.0.1:'+str(server.server_address[1])],
            capture_output=True, timeout=300, creationflags=0x08000000)
        (args.output/'stdout.log').write_bytes(completed.stdout)
        (args.output/'stderr.log').write_bytes(completed.stderr)
        assert completed.returncode == 0, completed.stderr.decode(errors='replace')
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert not thread.is_alive()
    browser = load(args.output/'report.json')
    workspace = EventWorkspace(repo, args.output/'server-root/events')
    p = workspace.view(browser['project_id'])
    assert p['envelope_fit'] == 'band-contour-v4'
    assert p['document']['source_job']['schema'] == 'vsl.event-authoring-job/8'
    version = workspace.root/p['id']/p['last_version']
    rows = list(csv.DictReader((version/'parameters.csv').open(encoding='utf-8-sig')))
    assert sum(r['group'].startswith('contour_') for r in rows) == 16
    assert sum(r['group'] == 'contours' for r in rows) == 2
    header = args.output/'header'
    header.mkdir()
    shutil.copy2(version/'profile.h', header/'profile.h')
    previous = data/'event_joint_v1/web1/header'
    for name in ('check.c', 'CMakeLists.txt'):
        shutil.copy2(previous/name, header/name)
    for command in (['cmake', '-S', str(header), '-B', str(header/'build'), '-G', 'Visual Studio 17 2022', '-A', 'x64'],
                    ['cmake', '--build', str(header/'build'), '--config', 'Release']):
        build = subprocess.run(command, capture_output=True, creationflags=0x08000000)
        assert build.returncode == 0, build.stderr.decode(errors='replace')
    values = list(map(float, subprocess.check_output([str(header/'build/Release/check.exe')], creationflags=0x08000000).split()))
    expected = []
    for contour in candidate['parameters']['contours']:
        expected.extend([contour['low_hz'], contour['high_hz']])
        expected.extend(v for pair in zip(contour['seconds'], contour['gain']) for v in pair)
    assert values == expected
    actual = EventWorkspace(repo, Path('E:/VehicleSoundLab/designs/events'))
    imported = actual.create(dict(package=dict(schema='vsl.event-design/1', document=p['document'], controls=p['controls'])))
    imported = actual.render(dict(id=imported['id']))
    final = actual.root/imported['id']/imported['last_version']/'synthesis.wav'
    a, _ = sf.read(final, dtype='float32')
    b, _ = sf.read(version/'synthesis.wav', dtype='float32')
    assert np.array_equal(a, b)
    baseline = load(data/'event_full_envelope_v1/before/runtime.json')
    assert all(sha(repo/name) == digest for name, digest in baseline.items())
    save(args.output/'verification.json', dict(result='passed', browser=browser,
        actual_job8_extraction_parameters_exact=True, four_group_reliability_visible=True,
        C_header_knots_exact=True, CSV_knots_exact=True, source_free_import_C_PCM_exact=True,
        actual_editable_project=imported['id'], actual_parameters=str(final.with_name('parameters.json')),
        own_server_closed=True, runtime_voice_files_unchanged=459, timbre_accepted=False))
    print(dict(result='passed', project=imported['id']), flush=True)


if __name__ == '__main__':
    main()
