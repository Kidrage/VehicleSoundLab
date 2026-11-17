"""Independent saved-waveform/coefficient audit, without projection-module imports."""
import argparse
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf
from scipy import signal

from research_archive_v1 import load, save, sha

EDGES = ((0,60), (60,300), (300,1200), (1200,4500), (4500,14000), (14000,24001))


def independent_bands(source, harmonic, remainder):
    n = 2048
    weight = np.hanning(n+1)[:-1]
    hz = np.fft.rfftfreq(n, 1/48000)
    scale = np.full(n//2+1, 2/(n*np.sum(weight*weight)))
    scale[[0,-1]] /= 2
    values = []
    for start in range(0, len(source)-n+1, 240):
        f, h, r = [np.fft.rfft(v[start:start+n]*weight[:,None], axis=0)
                   for v in (source, harmonic, remainder)]
        spectra = [(v.real**2+v.imag**2).mean(axis=1)*scale for v in (f,h,r)]
        spectra.append(2*(h.real*r.real+h.imag*r.imag).mean(axis=1)*scale)
        values.append([[float(v[(hz>=lo)&(hz<hi)].sum()) for lo,hi in EDGES] for v in spectra])
    # windows,source/projection/remainder/cross,bands
    return np.array(values)


def reconstruct(document):
    count = document['frames']
    t = np.arange(count)/document['sample_rate']
    result = np.zeros((count, document['channels']))
    coefficient = np.array(document['coefficients'])
    seconds = document['knots_seconds']
    grouped = {}
    for j, row in enumerate(document['columns']):
        grouped.setdefault((row['mode'],row['axis']), np.zeros((len(seconds), document['channels'])))[row['knot']] = coefficient[j]
    for (index, axis), gains in grouped.items():
        mode = document['modes'][index]
        sweep = document['sweep_seconds']
        hz = np.repeat(mode['hz'], count)
        if sweep:
            hz += (mode['end_hz']-mode['hz'])*np.minimum(t/sweep,1)
        # Integrate Hz first, as specified by the existing event phase contract.
        # Integrating radians instead changes long finite FP64 trajectories.
        integrated = signal.lfilter([1.], [1., -1.], hz)
        phase = mode['phase']+2*np.pi*np.r_[0., integrated[:-1]]/48000
        carrier = np.sin(phase) if axis=='sin' else np.cos(phase)
        for channel in range(document['channels']):
            result[:,channel] += carrier*np.interp(t,seconds,gains[:,channel])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,args.output/Path(__file__).name)
    report = dict(result='running',cases=[],goal_complete=False,timbre_accepted=False)
    save(args.output/'report.json',report)
    try:
        original = load(args.input/'report.json')
        assert original['result']=='passed'
        for case in original['cases']:
            root = args.input/case['kind']
            source, rate = sf.read(root/'source.wav',always_2d=True)
            assert rate==48000 and sha(root/'source.wav')==case['source_wave_sha256']
            assert sha(case['source']['path'])==case['source']['sha256']
            with sf.SoundFile(case['source']['path']) as stream:
                stream.seek(case['source']['first_frame'])
                raw=stream.read(len(source),always_2d=True)
            np.testing.assert_array_equal(raw,source)
            for model in case['models']:
                for split in ('full','interpolation'):
                    entry=model[split]
                    coeffpath=root/(model['id']+'-'+split+'.json')
                    assert sha(coeffpath)==entry['coefficients_sha256']
                    doc=load(coeffpath)
                    h, rate=sf.read(root/(model['id']+'-'+split+'-projection.wav'),always_2d=True)
                    r, _=sf.read(root/(model['id']+'-'+split+'-remainder.wav'),always_2d=True)
                    assert rate==48000
                    np.testing.assert_allclose(h+r,source,atol=2e-15,rtol=1e-14)
                    generated=reconstruct(doc)
                    error=float(abs(generated-h).max())
                    assert error<2e-10,error
                    measured=independent_bands(source,h,r)
                    expected=np.array([entry['bands'][j][key] for key in ('source','projection','remainder','cross') for j in range(6)]).reshape(4,6)
                    np.testing.assert_allclose(measured.mean(axis=0),expected,atol=1e-14,rtol=2e-11)
                    balance=float(abs(measured[:,0]-measured[:,1]-measured[:,2]-measured[:,3]).max())
                    assert balance<2e-13
                    masks={'all':np.ones(len(source),dtype=bool)}
                    if split=='interpolation':
                        masks['train']=(np.arange(len(source))//480)%4!=3
                        masks['withheld']=~masks['train']
                    for tag,mask in masks.items():
                        actual=1-float(np.mean(r[mask]**2)/np.mean(source[mask]**2))
                        assert abs(actual-entry['energy'][tag]['explained_SSE_fraction'])<1e-12
                    report['cases'].append(dict(kind=case['kind'],model=model['id'],split=split,
                        frames=len(source),coefficient_direct_error_FS=error,
                        spectral_balance_error_FS2=balance,source_wave_sha256=sha(root/'source.wav'),
                        projection_sha256=sha(root/(model['id']+'-'+split+'-projection.wav')),
                        remainder_sha256=sha(root/(model['id']+'-'+split+'-remainder.wav'))))
        report.update(result='passed',audited_projections=len(report['cases']),
            input_report_sha256=sha(args.input/'report.json'),no_runtime_or_qualification_change=True)
    except Exception as error:
        report.update(result='failed',error=repr(error))
        save(args.output/'report.json',report)
        raise
    save(args.output/'report.json',report)
    print('saved coefficients, source bindings and signed finite spectral budgets audited',flush=True)


if __name__=='__main__':main()
