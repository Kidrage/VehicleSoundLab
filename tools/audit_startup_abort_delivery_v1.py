"""Independently audit every frozen byte, version binding and cancellation audio."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            result.update(chunk)
    return result.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def float_mono(path):
    raw = Path(path).read_bytes()
    assert raw[:4] == b'RIFF' and raw[8:12] == b'WAVE'
    position = 12
    fmt = pcm = None
    while position+8 <= len(raw):
        name, count = struct.unpack_from('<4sI', raw, position)
        payload = raw[position+8:position+8+count]
        if name == b'fmt ':
            fmt = struct.unpack_from('<HHIIHH', payload)
        elif name == b'data':
            pcm = payload
        position += 8+count+(count & 1)
    assert fmt is not None and pcm is not None
    assert fmt[0] == 3 and fmt[1] == 1 and fmt[2] == 48000 and fmt[5] == 32
    return struct.unpack('<'+'f'*(len(pcm)//4), pcm)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = load(root/'manifest.json')
    declared = set()
    for row in manifest['files']:
        path = (root/row['path']).resolve()
        assert path.is_relative_to(root) and path.is_file(), row['path']
        assert row['path'] not in declared
        declared.add(row['path'])
        assert path.stat().st_size == row['bytes'] and digest(path) == row['sha256'], row['path']
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    assert actual == declared | {'manifest.json'}
    report = load(root/'repo/research/startup_abort_v1_verification.json')
    assert report['result'] == 'passed' and not report['goal_complete'] and not report['timbre_accepted']
    binaries = {digest(p) for p in (root/'binaries').rglob('*.dll')}
    checked = []
    for folder in sorted((root/'evidence').iterdir()):
        binding_path = folder/'source_binding.json'
        if not binding_path.is_file():
            continue
        binding = load(binding_path)
        assert binding['bridge_sha256'] in binaries
        for row in binding['files']:
            assert digest(folder/'exact_sources'/row['path']) == row['sha256']
        checked.append(folder.name)
    assert len(checked) == 14
    for name in ('fixed3', 'regression3', 'ui3', 'stop-fixture2', 'cycle2'):
        binding = load(root/'evidence'/name/'source_binding.json')
        assert binding['bridge_sha256'] == digest(root/'binaries/source-v5/vsl_source_bridge.dll')
        for row in binding['files']:
            assert digest(root/'repo'/row['path']) == row['sha256'], (name, row['path'])
    previous = root.parents[1]/'exhaust_return_v1/delivery1'
    for name in ('mix.wav', 'native.wav'):
        assert digest(root/'evidence/cycle2'/name) == digest(previous/'evidence/cycle2'/name)
    old = float_mono(root/'evidence/baseline1/events.wav')
    new = float_mono(root/'evidence/fixed3/events.wav')
    assert len(old) == len(new) == 192000
    assert max(map(abs, old[48000:])) > .001 and max(map(abs, new[22560:])) == 0
    events = load(root/'evidence/fixed3/abort.vsltake.json')['source_events']
    ends = [row for row in events if row['action'] == 2 and row['type'] == 2]
    assert len(ends) == 1 and ends[0]['frame'] == 22560 and ends[0]['reason'] == 1
    assert len(report['regression']['normal_original_v4_exact']) == 24
    assert report['unchanged_files']['voices'] == 89
    assert report['runtime_C_changed'] == ['modules/event_control/policy.c']
    for name in ('experiments/event_synth_v1/control_checks.c', 'modules/event_control/policy.c',
                 'modules/event_control/api.h', 'modules/event_control/scheduler.c'):
        assert digest(root/'evidence/final-test-build'/name) == digest(root/'repo'/name)
    assert report['ui']['final_state']['underflows'] == 0
    assert report['stop_fixture']['STOP_natural_tail_preserved']['frame'] == 60000
    result = dict(result='passed', files=len(declared), bytes=sum(x['bytes'] for x in manifest['files']),
                  manifest_sha256=digest(root/'manifest.json'), auditor_sha256=digest(__file__),
                  all_declared_bytes_checked=True, complete_file_set=True, source_bindings=len(checked),
                  old_and_final_binaries_preserved=True, actual_cancellation_wav_checked=True,
                  normal_full_cycle_exact=True, goal_complete=False, timbre_accepted=False)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
