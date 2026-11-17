"""Event context authoring, separate from parameter fitting and runtime DSP."""
import uuid
import soundfile as sf
from event_authoring.audio import read, sha
from event_authoring.context import probe
from event_authoring.band_scope import normalize
from .media import ranges
from .package import write_json


def intervals(data, duration):
    event, before = ranges(data, duration)
    _, after = ranges(dict(seconds=event, background_seconds=data.get('following_background_seconds')), duration)
    if before[1] > event[0] or after[0] < event[1]:
        raise ValueError('核查时请把第一段背景放在事件之前，第二段背景放在事件之后')
    return event, before, after


def make(folder, project, data):
    if not project.get('audio'):
        raise ValueError('请先导入包含前后背景的原录音片段')
    event, before, after = intervals(data, project['audio']['duration'])
    source = folder/'master.wav'
    if sha(source) != project['audio']['master_sha256']:
        raise ValueError('原录音身份已变化，请重新导入')
    scope = normalize(data.get('analysis_scope', project.get('analysis_scope')))
    report, _ = probe(source, event, dict(before=before, after=after), scope)
    context = [before[0], after[1]]
    audio, rate, origin = read(source, *context)
    run = 'context_'+uuid.uuid4().hex
    output = folder/run;output.mkdir()
    # Both files keep the original samples; monitor only applies the same
    # quarter gain as all existing workbench references, without fades or EQ.
    sf.write(output/'original.wav', audio, rate, subtype='FLOAT')
    sf.write(output/'monitor.wav', audio*.25, rate, subtype='FLOAT')
    report.update(event_seconds=event, before_seconds=before, after_seconds=after,
                  context_seconds=context, context_source=origin, monitor_gain=.25,
                  original_sha256=sha(output/'original.wav'), monitor_sha256=sha(output/'monitor.wav'))
    write_json(output/'report.json', report)
    return run, report


def matches(project):
    report = project.get('context_probe')
    if not report or not project.get('audio'):
        return None
    return (report['source']['sha256'] == project['audio']['master_sha256'] and
            report['event_seconds'] == project.get('selection') and
            report['before_seconds'] == project.get('background_selection') and
            report['after_seconds'] == project.get('following_background_selection') and
            normalize(report['analysis_scope']) == normalize(project.get('analysis_scope')))


def export_evidence(project):
    report=project.get('context_probe')
    if not report:return None
    document=project.get('document') or {}
    before=next(r['source'] for r in report['backgrounds'] if r['name']=='before')
    same=lambda a,b:bool(b) and all(a.get(k)==b.get(k) for k in ('sha256','first_frame','last_frame'))
    return dict(report=report,matches_current_selection=matches(project),
                matches_model_event_and_before_background=(same(report['source'],document.get('provenance')) and
                    same(before,document.get('background')) and normalize(report['analysis_scope'])==
                    normalize(document.get('source_job',{}).get('analysis_scope'))),
                following_background_used_for_fit=False)
