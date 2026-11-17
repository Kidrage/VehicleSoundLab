"""Fixed-rule transient screening; acoustic evidence, never a physical label."""
import numpy as np
from scipy import ndimage, signal


DETECTOR = dict(window=960, hop=240, local_median_frames=101,
                two_bands_above_db=6., min_spacing_seconds=.1)
FAMILIES = ('high', 'low_mid', 'short_high')
LOW_MID_BANDS = ((80, 300), (300, 1200), (1200, 3000))
SHORT_INTERVALS = dict(event=(-.004, .012), before=(-.15, -.05), after=(.05, .15))


def detector(mode='high'):
    if mode not in FAMILIES:
        raise ValueError('Unknown acoustic detector family')
    result = DETECTOR.copy()
    if mode == 'low_mid':
        result.update(family=mode, frequency_bands_hz=[list(b) for b in LOW_MID_BANDS])
    elif mode == 'short_high':
        result.update(family=mode, window=384, hop=48, local_median_frames=201,
                      min_spacing_seconds=.02,
                      frequency_bands_hz=[[1500,3000],[3000,6000],[6000,10000]],
                      intervals_seconds={key:list(value) for key,value in SHORT_INTERVALS.items()})
    return result


def peaks(audio, first_frame, rate=48000, mode='high'):
    config = detector(mode)
    if rate != 48000 or audio.ndim != 2 or len(audio) < config['window']:
        raise ValueError('Expected enough 48 kHz channel audio for the detector window')
    f, t, z = signal.stft(audio, fs=rate, nperseg=config['window'], noverlap=config['window']-config['hop'],
                           axis=0, boundary=None, padded=False)
    bands = LOW_MID_BANDS if mode == 'low_mid' else [(1500, 3000), (3000, 6000), (6000, 10000)]
    power = np.stack([(abs(z[(f >= lo) & (f < hi)])**2).sum(axis=0).mean(axis=0)
                      for lo, hi in bands])
    db = 10*np.log10(np.maximum(power, 1e-30))
    delta = db-ndimage.median_filter(db, size=(1, config['local_median_frames']), mode='nearest')
    score = np.sort(delta, axis=0)[-2]
    spacing = round(config['min_spacing_seconds']*rate/config['hop'])
    indices, _ = signal.find_peaks(score, height=config['two_bands_above_db'], distance=spacing)
    return [dict(source_seconds=float(first_frame/rate+t[k]),
                 two_band_prominence_db=float(score[k])) for k in indices]


def neighborhood(audio, event_frame, rate=48000, mode='high'):
    """Use unchanged fixed windows; don't search quieter backgrounds to pass."""
    detector(mode)
    intervals = SHORT_INTERVALS if mode == 'short_high' else dict(event=(-.025, .075), before=(-.35, -.15), after=(.16, .36))
    rows = {}
    for name, (lo, hi) in intervals.items():
        first, stop = event_frame+round(lo*rate), event_frame+round(hi*rate)
        if first < 0 or stop > len(audio):
            raise ValueError('Neighborhood audio does not contain fixed windows')
        x = audio[first:stop]
        rows[name] = dict(offset_seconds=[lo, hi],
                          mean_channel_power=float(np.mean(x*x)),
                          channel_peak=float(np.max(abs(x))))
    event = rows['event']['mean_channel_power']
    contrasts = {name:float(10*np.log10(max(event, 1e-30)/max(rows[name]['mean_channel_power'], 1e-30)))
                 for name in ('before', 'after')}
    return dict(windows=rows, contrast_db=contrasts,
                minimum_contrast_db=min(contrasts.values()),
                both_full_band_above_3db=all(v >= 3 for v in contrasts.values()),
                physical_identity_confirmed=False)


def scan_file(path, ranges=None, progress=None, mode='high'):
    """Stream fixed 30 s blocks; retain original detector lattice/windows."""
    import soundfile as sf
    configuration = detector(mode)
    with sf.SoundFile(path) as file:
        if file.samplerate != 48000 or file.channels not in (1, 2):
            raise ValueError('Expected an explicitly decoded 48 kHz mono/stereo master')
        total = len(file)
        if ranges is None:
            ranges = [[0., total/48000]]
        if not isinstance(ranges, list) or not ranges:
            raise ValueError('Expected nonempty scan ranges')
        for pair in ranges:
            if (not isinstance(pair, (list, tuple)) or len(pair) != 2 or
                any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in pair) or
                not np.isfinite(pair).all() or not 0 <= pair[0] < pair[1] <= total/48000):
                raise ValueError('Invalid source scan range')
        intervals = [tuple(round(v*48000) for v in pair) for pair in ranges]
        if any(lo >= hi for lo, hi in intervals):
            raise ValueError('Scan ranges must contain audio frames')
        if any(b[0] < x[1] for x, b in zip(sorted(intervals), sorted(intervals)[1:])):
            raise ValueError('Scan ranges must not overlap')
        rows, blocks = [], []
        for begin, end in intervals:
            for first in range(begin, end, 30*48000):
                last = min(end, first+30*48000)
                read_first, read_last = max(0, first-24000), min(total, last+24000)
                file.seek(read_first)
                audio = file.read(read_last-read_first, dtype='float64', always_2d=True)
                if not np.isfinite(audio).all():
                    raise ValueError('Source contains non-finite audio samples')
                retained = []
                for item in peaks(audio, read_first, mode=mode):
                    frame = round(item['source_seconds']*48000)
                    if not first <= frame < last or frame < 16800 or frame+17280 > total:
                        continue
                    nearby = neighborhood(audio, frame-read_first, mode=mode)
                    intervals = {key:[(frame+round(offset*48000))/48000 for offset in row['offset_seconds']]
                                 for key,row in nearby['windows'].items()}
                    row = dict(**item, **nearby,
                        classification='unclassified acoustic transient',
                        event_seconds=intervals['event'],
                        before_seconds=intervals['before'],
                        after_seconds=intervals['after'])
                    rows.append(row);retained.append(item['source_seconds'])
                block = dict(retain_seconds=[first/48000,last/48000],
                             read_frames=[read_first,read_last],candidates=retained)
                blocks.append(block)
                if progress is not None:progress(block)
    rows.sort(key=lambda r:r['source_seconds'])
    return dict(schema='vsl.event-candidate-scan/1', requested_ranges=ranges,
        sample_rate=48000, source_frames=total, detector=configuration,
        block_context_seconds=.5, blocks=blocks, candidates=rows,
        both_above_3db=sum(r['both_full_band_above_3db'] for r in rows),
        physical_identity_confirmed=False, fit_performed=False,
        limits=['Full-band contrast does not identify a physical event.',
            'Fixed 30 s block peak selection can differ within 100 ms of a block boundary.',
            'Fixed event and preceding/following windows; no search for quieter backgrounds.',
            'No source separation, cleaning, fitting, label inference or new download.'])
