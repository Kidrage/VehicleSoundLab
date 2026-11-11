"""Check source preservation and actual WAV channel policy from C renders."""
import json
import struct
import numpy as np
import soundfile as sf


def read(path, channels=None):
    audio, rate = sf.read(path, always_2d=True, dtype='float32')
    assert rate == 48000 and np.isfinite(audio).all()
    if channels:
        assert audio.shape[1] == channels
    return audio


def channel_mask(path):
    with path.open('rb') as file:
        assert file.read(4) == b'RIFF'
        file.read(4)
        assert file.read(4) == b'WAVE'
        while True:
            tag, size = struct.unpack('<4sI', file.read(8))
            data = file.read(size)
            if tag == b'fmt ':
                assert struct.unpack_from('<H', data)[0] == 65534
                return struct.unpack_from('<I', data, 20)[0]
            if size & 1:
                file.read(1)


def check(workspace, output, records, frames):
    raw = output / 'raw'
    get = lambda case, stem: read(raw / f'{case}_{stem}.wav')
    dna = get('pair_dry', 'dna_raw')
    low = get('pair_dry', 'low_raw')
    frozen = workspace / 'references/analysis/coherent_low_v1/raw'
    assert np.array_equal(dna, read(frozen / 'dna.wav')[:frames])
    assert np.array_equal(low, read(frozen / 'measured.wav')[:frames])
    objects = ['exhaust_left', 'exhaust_right', 'intake', 'body', 'mechanical',
               'air_left', 'air_right', 'events', 'road', 'wind']
    cases = ['pair_room', 'pair_geometry', 'left_geometry', 'right_geometry', 'bed_dry', 'bed_room']
    for case in cases:
        assert np.array_equal(dna, get(case, 'dna_raw'))
        assert np.array_equal(low, get(case, 'low_raw'))
        assert np.array_equal(get('pair_dry', 'dry'), get(case, 'dry'))
        if case not in ('left_geometry', 'right_geometry'):
            for obj in objects:
                assert np.array_equal(get('pair_dry', obj), get(case, obj))
    for obj in objects[2:]:
        assert np.count_nonzero(get('pair_dry', obj)) == 0
    pair = get('pair_dry', 'render')
    assert np.max(abs(pair[:, 0] - pair[:, 1])) < 1e-7
    left, right = get('left_geometry', 'render'), get('right_geometry', 'render')
    mirror_error = float(np.max(abs(left - right[:, ::-1])))
    assert mirror_error < 1e-7
    bed = read(raw / 'bed_dry_render.wav', 12)
    room = read(raw / 'bed_room_render.wav', 12)
    assert np.count_nonzero(bed[:, 8:]) == 0
    height_rms = np.sqrt(np.mean(room[:, 8:].astype('float64') ** 2, axis=0))
    assert np.all(height_rms > 1e-5)
    assert channel_mask(raw / 'bed_room_render.wav') == 0x2d63f
    peaks = {}
    for name, record in records.items():
        audio = read(raw / f'{name}_render.wav', record['settings']['channels'])
        assert len(audio) == frames and record['probe']['source_frame'] == frames
        assert record['probe']['legacy_frame'] == 0
        peak = float(np.max(abs(audio)))
        assert peak < .95
        peaks[name] = peak
    for case in ('warm', 'hollow'):
        assert np.count_nonzero(get(case, 'low_raw')) == 0
    return dict(accepted_DNA_float_equal=True, accepted_LF_float_equal=True,
                spatial_controls_leave_raw_and_pre_spatial_stems_identical=True,
                dry_monitor_equal_across_layouts=True, legacy_drive_never_ticked=True,
                symmetric_pair_difference_max=float(np.max(abs(pair[:, 0] - pair[:, 1]))),
                single_outlet_mirror_error=mirror_error, unused_objects_silent=True,
                dry_heights_silent=True, room_height_rms=height_rms.tolist(),
                wave_speaker_mask='0x2d63f',
                channel_order=['FL', 'FR', 'FC', 'LFE', 'BL', 'BR', 'SL', 'SR', 'TFL', 'TFR', 'TBL', 'TBR'],
                peaks=peaks, clipping=False,
                synthetic_fixtures='Warm/Hollow exercise the same C adapter; not additional measured real engines')
