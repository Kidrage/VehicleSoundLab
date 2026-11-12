"""Bind approved observations, frozen acoustic coordinates and current models."""
import csv
import json
from pathlib import Path
from drive_evidence_v1.sources import sha


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def frozen(workspace, baseline, names):
    root = workspace/'baselines'/baseline
    manifest = root/'manifest.json'
    mapping = {v['path']: v['sha256'] for v in read_json(manifest)['files']}
    files = {str(manifest): sha(manifest)}
    result = {}
    for name in names:
        path = root/name
        assert sha(path) == mapping[name], name
        files[str(path)] = mapping[name]
        result[name] = read_json(path)
    return result, files


def bind(workspace, repo, plan):
    paths, hashes = frozen(workspace, 'drive_evidence_v1', [
        'evidence/summary_v3/report.json', 'evidence/summary_v3/verification.json',
        'evidence/observed/E_video/frames.json'])
    report = paths['evidence/summary_v3/report.json']
    verified = paths['evidence/summary_v3/verification.json']
    assert verified['result'] == 'pass'
    # Old verification predates later strict source identities; the manifest
    # binds its exact bytes, and all required source media are checked anew.
    rows = report['family']['rows']
    assert report['family']['status'] == 'connected_observed_family'
    video = paths['evidence/observed/E_video/frames.json']
    catalog = read_json(repo/'references/segments_v1.json')
    media = workspace/catalog['sources']['E']['video']
    assert sha(media) == video['video_sha256'] == catalog['sources']['E']['video_sha256']
    hashes[str(media)] = sha(media)
    annotation = repo/'research/acceleration_passage_v1_annotations.json'
    labels = read_json(annotation)
    hashes[str(annotation)] = sha(annotation)
    frames = []
    directory = workspace/'baselines/drive_evidence_v1/evidence/observed/E_video'
    for row in labels['observations']:
        frame = next(v for v in video['frames'] if abs(v['source_seconds']-row['seconds']) < 1e-8)
        path = directory/frame['file']
        assert sha(path) == frame['sha256']
        hashes[str(path)] = frame['sha256']
        frames.append(frame | row)
    speed = [v['dash_kmh'] for v in frames]
    assert all(v['gear'] == 5 for v in frames)
    assert all(b > a for a, b in zip(speed, speed[1:]))
    lo, hi = plan['audio_seconds']
    dlo, dhi = plan['display_minus_audio_sensitivity_seconds']
    # display_time=audio_time+offset. The whole selected audio interval is
    # inside the observed same-gear span for every offset in this envelope.
    safe = [plan['display_gear5_interval_seconds'][0]-dlo,
            plan['display_gear5_interval_seconds'][1]-dhi]
    assert safe[0] <= lo < hi <= safe[1]
    index = repo/plan['models']
    hashes[str(index)] = sha(index)
    models = []
    for voice in read_json(index)['voices']:
        path = index.parent/voice['file']
        assert sha(path) == voice['model_sha256']
        hashes[str(path)] = sha(path)
        models.append(path)
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as stream:
        c_index = list(csv.DictReader(stream))
    assert len(c_index) == 478
    for row in c_index:
        assert sha(repo/row['文件']) == row['SHA-256'], row['文件']
    return rows, models, hashes, dict(frames=frames,
        safe_audio_interval_under_assumed_offset=safe, observed_display_speed_kmh=[speed[0], speed[-1]],
        display_observation_span=[frames[0]['seconds'], frames[-1]['seconds']],
        C_H_unchanged=len(c_index), source_only_not_driver_validation=True)
