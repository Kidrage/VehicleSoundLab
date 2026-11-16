"""Analytic clocks and unchanged eight analytic recorded-context fixtures."""
import numpy as np
from research_archive_v1 import load, sha
from exterior_clock_v1.warp import render_positions
from recorded_phase_context_v1.fixtures import formula, cycles
from recorded_phase_context_v1.metrics import heldout
from locked_source_tail_v1.known import evaluate as tones
from .geometry import build, evaluate, from_context, summary


def analytic_clock(q, origin, kind):
    y = origin+q/65536
    if kind == 'chirp':
        y = y+1e-10*(q-8192)**2
    elif kind == 'modulated':
        y = y+2e-5*np.sin(q/1700)
    elif kind == 'C0':
        nodes = np.array([1024.25, 4096.5, 8192.125, 12288.75, 16384.3])
        jumps = np.array([1e-8, -6e-9, 4e-9, -7e-9, 3e-9])
        y = y+np.maximum(q[:, None]-nodes, 0)@jumps
    return y


def analytic_suite(out, coeff, freqs, taps):
    x, q = np.arange(-2048, 20481, 256, dtype=float), np.arange(18434, dtype=float)
    cases = []
    for origin in (.36, 160.36):
        for kind in ('affine', 'chirp', 'modulated', 'C0'):
            model = build(x, analytic_clock(x, origin, kind))
            positions = evaluate(model, q)
            exact = analytic_clock(q, origin, kind)
            base = 160. if origin > 1 else 0.
            signals = dict(stereo=tones(positions-base, freqs, coeff, taps),
                mono=tones(positions-base, freqs, np.repeat(coeff[:, :1], 2, axis=1), taps),
                zero=tones(positions-base, freqs, coeff*0, taps),
                weak=tones(positions-base, freqs, coeff*1e-6, taps))
            delayed = coeff.copy(); delayed[:, 1] *= np.exp(-2j*np.pi*freqs*.00035)
            signals['delayed'] = tones(positions-base, freqs, delayed, taps)
            truth = tones(exact-base, freqs, coeff, taps)
            wave = float(np.linalg.norm(signals['stereo']-truth)/np.linalg.norm(truth))
            if kind != 'C0':
                assert wave < .005
            assert np.array_equal(signals['mono'][:, 0], signals['mono'][:, 1])
            assert not np.count_nonzero(signals['zero'])
            file = out/(kind+('_large' if base else '')+'.npz')
            np.savez_compressed(file, **model, query=q, positions=positions, exact=exact,
                frequencies=freqs, tone_coefficients=coeff, taps=taps, truth=truth,
                **{'signal__'+k:v for k,v in signals.items()})
            cases.append(dict(file=file.name, sha256=sha(file), kind=kind, origin=origin,
                wave_change_vs_analytic_NRMSE=wave,
                qualified=True, **summary(model, q, positions, exact)))
    rejected = []
    y = analytic_clock(x, .36, 'affine')
    for name, xx, yy in (
        ('complex', x.astype(complex), y), ('nonfinite', x*np.nan, y),
        ('duplicate', np.r_[x[0], x[:-1]], y), ('reverse_x', x[::-1], y),
        ('flat_y', x, y*0), ('reverse_y', x, y[::-1]),
        ('too_short', x[:2], y[:2])):
        try:
            build(xx, yy)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError(name)
    for name, query in (('left', x[:1]-1), ('right', x[-1:]+1),
                        ('nan_query', np.array([np.nan])), ('complex_query', x.astype(complex)),
                        ('empty_query', np.empty(0))):
        try:
            evaluate(build(x, y), query)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError(name)
    return dict(cases=cases, rejections=rejected, all_known_qualified=True)


def recorded_suite(out, workspace, binding):
    root = workspace/'baselines/recorded_phase_context_v1/evidence'
    report = binding(root/'known1/report.json'); proof = binding(root/'known_audit2/report.json')
    assert proof['all_qualified'] and proof['producer_sha256'] == sha(root/'known1/report.json')
    cases = []
    for row in report['cases']:
        path = root/'known1'/row['file']; binding(path, row['sha256'])
        with np.load(path) as z:
            d = {k:z[k] for k in z.files}
        model = from_context(d)
        positions = evaluate(model, d['sample_indices'])
        validation = evaluate(model, d['validation_indices'])
        cutoff = row['info']['cutoff_hz']
        audio = render_positions(d['native'], 0., positions, cutoff)
        va = render_positions(d['native'], 0., validation, cutoff)
        h = heldout(dict(sample_indices=d['sample_indices'], validation_indices=d['validation_indices'], validation_audio=va))
        minimum = min(min(v['coherence']) for t in h.values() for v in t.values())
        residual = cycles(positions, row['spec'])-d['sample_indices']/1024
        exact = formula(positions, row['spec'])
        error = float(np.linalg.norm(audio-exact)/np.linalg.norm(exact))
        std = float(np.std(residual))
        qualified = minimum > .99 and std < .002 and error < .005
        file = out/('fixture_'+row['label']+'.npz')
        np.savez_compressed(file, **model, query=d['sample_indices'], positions=positions,
            validation_query=d['validation_indices'], validation_positions=validation,
            audio=audio, validation_audio=va)
        cases.append(dict(label=row['label'], file=file.name, sha256=sha(file), source=str(path),
            spec=row['spec'], cutoff=cutoff, heldout=h, minimum_heldout_coherence=minimum,
            cycle_residual_std=std, analytic_wave_NRMSE=error, qualified=bool(qualified),
            **summary(model, d['sample_indices'], positions, d['positions'])))
        print('C1_KNOWN', row['label'], qualified, std, error, minimum, flush=True)
    assert all(c['qualified'] for c in cases)
    return dict(cases=cases, all_known_qualified=True)
