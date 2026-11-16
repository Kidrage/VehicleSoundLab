"""Original C1 controls + source-FIR native references, before real material."""
import numpy as np
from scipy import signal
from clock_c1_v1.geometry import build, evaluate
from locked_source_tail_v1.known import evaluate as tones


def generate(workspace, read, arrays):
    root = workspace/'references/analysis/clock_c1_v1/known1'
    info = read(root/'report.json')
    prior = read(root.parent/'known_audit1/report.json')
    assert prior['verification_passed'] and prior['all_known_qualified']
    for row in info['analytic']['cases']:
        d = arrays(read(root/row['file'], row['sha256']))
        yield dict(label='clock_'+row['file'][:-4], family='analytic', model=d,
            query=d['query'], source=d['signal__stereo'], source_origin=160. if row['origin'] > 1 else 0.,
            frequencies=d['frequencies'], coefficients=d['tone_coefficients'], source_taps=d['taps'],
            count=8192, original_model=str(root/row['file']))
    row = info['analytic']['cases'][0]; d = arrays(read(root/row['file'], row['sha256']))
    for variant in ('mono', 'zero', 'weak', 'delayed'):
        coeff = d['tone_coefficients'].copy()
        if variant == 'mono': coeff[:, 1] = coeff[:, 0]
        if variant == 'zero': coeff *= 0
        if variant == 'weak': coeff *= 1e-6
        if variant == 'delayed': coeff[:, 1] *= np.exp(-2j*np.pi*d['frequencies']*.00035)
        yield dict(label='path_'+variant, family='analytic', model=d, query=d['query'],
            source=d['signal__'+variant], source_origin=0., frequencies=d['frequencies'],
            coefficients=coeff, source_taps=d['taps'], count=8192, original_model=str(root/row['file']))
    x = np.arange(-2048, 20481, 256, dtype=float)
    model = build(x, 17+x/(1024*128))
    q = np.arange(18434, dtype=float)
    for label, freq in (('near_Nyquist', np.array([19456., 20480., 22016., 23552., 24576., 28032.])),
                        ('pure_stopband', np.array([25984.]))):
        coeff = np.array([[.09/(1+.4*i)*np.exp(.13j*(i+1)), .61*.09/(1+.4*i)*np.exp(1j*(.13*(i+1)+.37))]
                          for i in range(len(freq))])
        yield dict(label=label, family='analytic', model=model, query=q,
            source=tones(evaluate(model, q)-17, freq, coeff), source_origin=17.,
            frequencies=freq, coefficients=coeff, source_taps=np.array([1.]), count=4096, original_model=None)
    for row in info['recorded']['cases']:
        d = arrays(read(root/row['file'], row['sha256']))
        original = arrays(read(row['source']))
        kernel = signal.firwin(1025, row['cutoff'], fs=48000, window=('kaiser', 12))
        filtered = signal.fftconvolve(original['native'], kernel[:, None], mode='same', axes=0)
        start = np.ceil(evaluate(d, d['query'][4096:4097])[0]*48000)/48000
        first = int(round(start*48000)); count = 8192
        assert first-512 >= 0 and first+count+512 <= len(original['native'])
        yield dict(label='recorded_'+row['label'], family='recorded', model=d,
            query=d['query'], source=d['audio'], native_start=float(start), count=count,
            raw=original['native'][first:first+count], reference=filtered[first:first+count],
            source_taps=kernel, source_native=original['native'], first=first,
            original_model=str(root/row['file']), original_source=row['source'], spec=row['spec'])
