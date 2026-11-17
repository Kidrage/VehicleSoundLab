"""One-player lifecycle review from captured C stems and actual telemetry."""
import csv
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf


def build(capture, output):
    capture, output = Path(capture), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = json.loads((capture/'verification.json').read_text(encoding='utf-8'))
    if not all(item['passed'] for item in report['checks']):
        raise ValueError('Review requires a passed capture; retain failed evidence separately')
    stems = report['native_stems']
    packed, rate = sf.read(capture/'native.wav', dtype='float32', always_2d=True)
    if rate != 48000 or packed.shape != (report['frames'], report['native_channels']):
        raise ValueError('Native capture shape changed')
    tracks = {}
    offset = 0
    for row in stems:
        tracks[row['name']] = packed[:, offset:offset+row['channels']]
        offset += row['channels']
    events = np.zeros((len(packed), 2))
    for k in range(4):
        events += tracks['event_'+str(k)].astype(float) * 2**-.5
    event_rms = float(np.sqrt(np.mean(events**2)))
    files = [('mix', '完整干声', None), ('dna', 'DNA 主声线', tracks['dna']),
             ('low', '低频层', tracks['low']), ('detail', '细节层', tracks['detail']),
             ('idle', '怠速附加声线', tracks['added']), ('events', '独立事件', events)]
    exports = []
    for key, name, audio in files:
        path = output/(key+'.wav')
        if audio is None:
            shutil.copy2(capture/'mix.wav', path)
        else:
            sf.write(path, audio, rate, subtype='FLOAT')
        exports.append(dict(id=key, name=name, file=path.name,
                            sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    rows = list(csv.DictReader((capture/'telemetry.csv').open(encoding='utf-8', newline='')))
    data = []
    for row in rows[::4]:
        data.append([float(row['seconds']), float(row['rpm']), float(row['speed_mps'])*3.6,
                     int(row['gear']), row['lifecycle_name'], row['operating_name'],
                     float(row['throttle_request']), float(row['brake_request']),
                     float(row['idle_weight']), int(row['overruns'])])
    scenario = json.loads((capture/'scenario.json').read_text(encoding='utf-8'))
    value = dict(schema='vsl.vehicle-lifecycle-review/1', sample_rate=rate,
                 duration=report['frames']/rate, tracks=exports, telemetry=data,
                 telemetry_columns=['seconds','rpm','speed_kph','gear','lifecycle','operating',
                                    'throttle','brake','idle_weight','overruns'],
                 stages=scenario['stages'], independent_event_rms=event_rms,
                 bridge_sha256=report['bridge_sha256'], source_capture=str(capture),
                 extra_monitor_gain=1., independent_normalization=False, spatial_processing=False,
                 event_profiles=report.get('event_profile_description',
                     'Only unaccepted real-A crank/catch candidates; afterfire and shift one-shots unavailable.'),
                 introduction=report.get('review_introduction',
                     '行驶为当前配方，启动与接火为待听评候选。回火、换挡独立短声尚无实车参数，当前留空。转速来自演示控制，不是原车实测轨迹。'),
                 listening_hint=report.get('review_listening_hint',
                     '先听完整干声，再切换各层。切换保留当前时间；独立事件仅在启动阶段发声。'),
                 timbre_accepted=False, goal_complete=False)
    (output/'data.js').write_text('window.VSL_LIFECYCLE = '+json.dumps(value, ensure_ascii=False, separators=(',',':'))+';\n', encoding='utf-8')
    for name in ('lifecycle.vsltake.json', 'telemetry.csv', 'scenario.json', 'verification.json'):
        shutil.copy2(capture/name, output/name)
    web = Path(__file__).with_name('web')
    for path in web.iterdir():
        shutil.copy2(path, output/path.name)
    (output/'manifest.json').write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    return value
