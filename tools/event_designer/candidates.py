"""Candidate discovery and explicit selection, independent of fitting/DSP."""
import json
from pathlib import Path
import shutil
import uuid
from event_authoring.audio import sha
from event_authoring.scan import scan_file
from .package import write_json


def make(folder, project):
    if not project.get('audio'):
        raise ValueError('请先导入包含事件与附近背景的音频片段')
    source = folder/'master.wav'
    if sha(source) != project['audio']['master_sha256']:
        raise ValueError('原录音身份已变化，请重新导入')
    report = scan_file(source, mode=project.get('scan_detector', 'high'))
    report.update(source_sha256=project['audio']['master_sha256'],
                  source_filename=project['audio']['filename'])
    run = 'scan_'+uuid.uuid4().hex
    output = folder/run;output.mkdir()
    exact = output/'exact_sources';exact.mkdir()
    for path in (Path(__file__), Path(__file__).parents[1]/'event_authoring/scan.py'):
        shutil.copy2(path, exact/path.name)
    report['execution_sources'] = {p.name:sha(p) for p in exact.glob('*.py')}
    write_json(output/'report.json', report)
    return run, sha(output/'report.json'), report


def selected(folder, project, data):
    run = project.get('scan_run')
    if not run or data.get('scan_run') != run:
        raise ValueError('候选列表已变化，请重新选择')
    path = folder/run/'report.json'
    if sha(path) != project.get('scan_sha256'):
        raise ValueError('候选记录身份已变化，请重新扫描')
    report = json.loads(path.read_text(encoding='utf-8'))
    if (report['source_sha256'] != project['audio']['master_sha256'] or
        sha(folder/'master.wav') != report['source_sha256']):
        raise ValueError('候选与当前原录音不匹配')
    index = data.get('candidate_index')
    if type(index) is not int or not 0 <= index < len(report['candidates']):
        raise ValueError('无效候选编号')
    return report['candidates'][index]


def export_evidence(project):
    report = project.get('candidate_scan')
    if not report:return None
    row = project.get('selected_candidate')
    matched = bool(row) and (row['scan_run'] == project.get('scan_run') and
        row['event_seconds'] == project.get('selection') and
        row['before_seconds'] == project.get('background_selection') and
        row['after_seconds'] == project.get('following_background_selection'))
    return dict(report=report, selected_candidate=row, matches_current_selection=matched,
                physical_identity_confirmed=False, scan_sha256=project['scan_sha256'])
