"""Verify literal V10/V12 startup trigger and signal edges; not a Max emulator."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--fetch', type=Path, required=True)
parser.add_argument('--routes', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


fetch = json.loads((args.fetch/'report.json').read_text(encoding='utf-8'))
routes = json.loads(args.routes.read_text(encoding='utf-8'))
assert fetch['result'] == routes['result'] == 'pass'
assert routes['fetch_report_sha256'] == sha(args.fetch/'report.json')
for row in fetch['files']:
    assert sha(args.fetch/'text'/row['path']) == row['sha256'], row['path']
args.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, args.out/'executed_inspector.py')
report = dict(schema='vsl.v6-startup-static-audit/1', result='running',
    revision=fetch['revision'], fetch_report_sha256=sha(args.fetch/'report.json'),
    route_report_sha256=sha(args.routes), source_sha256=sha(__file__), profiles=[])


def inspect(profile):
    root = args.fetch/'text'
    traces = []

    def patch(name):
        p = json.loads((root/name).read_text(encoding='utf-8-sig'))['patcher']
        return p, {r['box']['id']:r['box'] for r in p['boxes']}

    def trace(file, label, edges, expected=None):
        p, nodes = patch(file)
        actual = {(r['patchline']['source'][0], r['patchline']['source'][1],
                   r['patchline']['destination'][0], r['patchline']['destination'][1])
                  for r in p.get('lines', [])}
        for edge in edges:
            assert tuple(edge) in actual, (file, label, edge)
        for node, text in (expected or {}).items():
            assert nodes[node].get('text') == text, (file, node, text)
        used = sorted({e[i] for e in edges for i in (0, 2)})
        traces.append(dict(file=file, label=label, edges=edges,
            nodes={k:{f:v for f,v in nodes[k].items() if f in
                ('id','text','maxclass','items','value','name')} for k in used}))

    # Message outlets are zero based. Cold int inlet stores style without firing.
    transient = f'patchers/transient_{profile}~.maxpat'
    trace(transient, 'fresh style initialization', [
        ['obj-10',0,'obj-6',0], ['obj-6',0,'obj-8',0], ['obj-8',0,'obj-7',1],
        ['obj-6',1,'obj-9',0], ['obj-9',0,'obj-7',1], ['obj-3',1,'obj-6',0]],
        {'obj-10':'loadmess cinematic', 'obj-6':'sel cinematic realistic', 'obj-7':'int 1'})
    trace(transient, 'starter=1 selects stored style', [
        ['obj-2',0,'obj-3',0], ['obj-3',0,'obj-5',0], ['obj-5',0,'obj-7',0],
        ['obj-7',0,'obj-11',0], ['obj-11',1,'obj-44',0], ['obj-44',0,'obj-45',0]],
        {'obj-5':'sel 1 0', 'obj-11':'sel 1 2', 'obj-44':'start',
         'obj-45':f'play~ starter_{profile} 1'})
    trace(transient, 'procedural cinematic trigger and style gain', [
        ['obj-11',0,'obj-20',0], ['obj-20',0,'obj-21',0], ['obj-21',0,'obj-24',0],
        ['obj-24',0,'obj-25',0], ['obj-25',0,'obj-19',1],
        ['obj-8',0,'obj-16',0], ['obj-9',0,'obj-17',0], ['obj-16',0,'obj-18',0],
        ['obj-17',0,'obj-18',0], ['obj-18',0,'obj-30',0], ['obj-30',0,'obj-31',0],
        ['obj-31',0,'obj-32',1], ['obj-31',0,'obj-33',1]],
        {'obj-19':f'{profile}_engine_start_v3_beap~', 'obj-16':'1. 15', 'obj-17':'0. 15'})
    trace(transient, 'starter sample filter and fixed scale', [
        ['obj-45',0,'obj-46',0], ['obj-46',0,'obj-47',0]],
        {'obj-46':'lores~ 1800 0.65', 'obj-47':'*~ 0.75'})
    if profile == 'v10':
        trace(transient, 'realistic also starts local stereo sample', [
            ['obj-11',1,'obj-59',0], ['obj-59',0,'obj-60',0],
            ['obj-60',0,'obj-61',0], ['obj-60',1,'obj-62',0]],
            {'obj-59':'start', 'obj-60':'play~ ferrari_startup 2',
             'obj-61':'*~ 0.65', 'obj-62':'*~ 0.65'})
        trace(transient, 'metadata-controlled sample selection', [
            ['obj-48',0,'obj-49',0], ['obj-49',0,'obj-50',0], ['obj-58',1,'obj-50',0],
            ['obj-50',6,'obj-51',0], ['obj-51',0,'obj-52',0], ['obj-52',0,'obj-53',0],
            ['obj-51',0,'obj-54',0], ['obj-54',0,'obj-55',0], ['obj-55',0,'obj-56',0],
            ['obj-56',0,'obj-57',1], ['obj-53',0,'obj-63',1], ['obj-53',0,'obj-64',1]],
            {'obj-50':'info~ ferrari_startup', 'obj-51':'expr $f1>500.', 'obj-54':'expr 1.-$f1'})
        trace(transient, 'sample audio reaches transient outlets', [
            ['obj-47',0,'obj-57',0], ['obj-57',0,'obj-65',0], ['obj-57',0,'obj-66',0],
            ['obj-61',0,'obj-63',0], ['obj-62',0,'obj-64',0],
            ['obj-63',0,'obj-65',1], ['obj-64',0,'obj-66',1],
            ['obj-65',0,'obj-68',1], ['obj-66',0,'obj-69',1],
            ['obj-68',0,'obj-75',0], ['obj-69',0,'obj-76',0],
            ['obj-75',0,'obj-77',1], ['obj-76',0,'obj-78',1],
            ['obj-77',0,'obj-79',0], ['obj-78',0,'obj-80',0]])
        gain = (74,70,71,72,73,75,76)
        stop, stop_target = 67, 25
    else:
        trace(transient, 'sample audio reaches transient outlets', [
            ['obj-47',0,'obj-49',1], ['obj-47',0,'obj-50',1],
            ['obj-49',0,'obj-56',0], ['obj-50',0,'obj-57',0],
            ['obj-56',0,'obj-58',1], ['obj-57',0,'obj-59',1],
            ['obj-58',0,'obj-60',0], ['obj-59',0,'obj-61',0]])
        gain = (55,51,52,53,54,56,57)
        stop, stop_target = 48, 25
    init,clip,db,pack,line,left,right = [f'obj-{i}' for i in gain]
    trace(transient, 'startup level default and conversion', [
        [init,0,clip,0], ['obj-3',2,clip,0], [clip,0,db,0], [db,0,pack,0],
        [pack,0,line,0], [line,0,left,1], [line,0,right,1]],
        {init:'loadmess -5', db:'expr pow(10., $f1/20.)'})
    trace(transient, 'starter=0 stops only procedural envelope here', [
        ['obj-5',1,f'obj-{stop}',0], [f'obj-{stop}',0,f'obj-{stop_target}',0]],
        {f'obj-{stop}':'0. 150'})

    p,nodes = patch(transient)
    reads = [n['id'] for n in nodes.values() if n.get('text','').startswith('play~ ')]
    reader_inputs = [r['patchline'] for r in p['lines'] if r['patchline']['destination'][0] in reads]
    assert all(r['source'][0] in ('obj-44','obj-59') for r in reader_inputs)
    assert not any(r['patchline']['source'][0] == 'obj-15' for r in p['lines'])
    controller = f'patchers/engine_controller_{profile}.maxpat'
    trace(controller, 'ignition/start eligibility emits starter messages', [
        ['obj-4',0,'obj-6',0], ['obj-4',1,'obj-8',0],
        ['obj-6',0,'obj-10',1], ['obj-8',0,'obj-10',0],
        ['obj-10',0,'obj-11',0], ['obj-11',0,'obj-12',0], ['obj-12',0,'obj-13',0],
        ['obj-13',2,'obj-16',0], ['obj-16',0,'obj-5',0],
        ['obj-19',0,'obj-20',0], ['obj-20',2,'obj-21',0], ['obj-21',0,'obj-5',0]],
        {'obj-10':'pak 0 0 1', 'obj-11':'expr $i1*$i2*$i3',
         'obj-16':'starter 1', 'obj-21':'starter 0'})

    wrapper = f'patchers/vehicle_engine_{profile}~.maxpat'
    trace(wrapper, 'controller broadcast to transient', [
        ['obj-3',0,'obj-4',0], ['obj-4',4,'obj-8',0]],
        {'obj-3':f'engine_controller_{profile}', 'obj-8':f'transient_{profile}~'})
    trace(wrapper, 'transient through solo gates/cabin/EQ/master to public outlets', [
        ['obj-8',0,'obj-53',0], ['obj-8',1,'obj-54',0],
        ['obj-47',0,'obj-53',1], ['obj-47',0,'obj-54',1],
        ['obj-53',0,'obj-14',1], ['obj-54',0,'obj-17',1],
        ['obj-14',0,'obj-15',0], ['obj-15',0,'obj-16',0],
        ['obj-17',0,'obj-18',0], ['obj-18',0,'obj-19',0],
        ['obj-16',0,'obj-11',1], ['obj-19',0,'obj-11',2],
        ['obj-11',0,'obj-12',1], ['obj-11',1,'obj-12',2],
        ['obj-12',0,'obj-13',1], ['obj-12',1,'obj-13',2],
        ['obj-13',0,'obj-20',0], ['obj-13',1,'obj-21',0]])
    trace(wrapper, 'fresh solo defaults permit transient before downstream gains', [
        ['obj-50',0,'obj-34',0], ['obj-50',0,'obj-35',0], ['obj-50',0,'obj-36',0],
        ['obj-34',0,'obj-37',0], ['obj-35',0,'obj-37',1], ['obj-36',0,'obj-37',2],
        ['obj-37',0,'obj-40',0], ['obj-40',0,'obj-46',0], ['obj-46',0,'obj-47',0]],
        {'obj-50':'loadmess 0', 'obj-37':'pak 0 0 0', 'obj-40':'expr (1-$i3)*(1-$i1*(1-$i2))'})
    entry = f'VehicleSoundSynth-{profile.upper()}.maxpat'
    trace(entry, 'public menu fresh default is cinematic', [
        ['obj-60',0,'obj-56',0], ['obj-56',0,'obj-57',0],
        ['obj-57',0,'obj-58',0], ['obj-57',1,'obj-59',0],
        ['obj-58',0,'obj-15',0], ['obj-59',0,'obj-15',0]],
        {'obj-60':'loadmess 0', 'obj-58':'start_style cinematic', 'obj-59':'start_style realistic'})
    return dict(profile=profile, default_sample_start_on_starter1=False,
        realistic_style_starts_samples=True, startup_level_default_db=-5,
        reader_input_edges=reader_inputs, traces=traces,
        disconnected_starter_signal_node='obj-15 rampsmooth~ 64 256',
        sample_audio_has_style_or_starter_stop_gate=False,
        caveat='Static patch edges only. Media loading, BEAP internals, saved/runtime state and actual audibility not executed.')


try:
    for profile in ('v10','v12'):
        report['profiles'].append(inspect(profile))
    report.update(result='pass', runtime_changed=False, media_fetched=False,
        limits=['No Max runtime/audio execution; explicit fresh literal defaults only',
            'V10 info~ outlet 6 threshold is traced as coded; no media validity/metadata execution',
            'Reachable sample startup is distinct from public procedural DNA',
            'No claim that every external BEAP implementation or arbitrary runtime state is sample-free',
            'No timbre acceptance or C/model/UI/state-map changes'])
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(dict(result=report['result'], profiles=[dict(profile=r['profile'],
    traces=len(r['traces']), default_sample_start=r['default_sample_start_on_starter1'])
    for r in report['profiles']])))
