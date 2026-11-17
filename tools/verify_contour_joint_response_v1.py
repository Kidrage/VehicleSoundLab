"""Known-source and affine-response checks for the optional simultaneous fit."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

import numpy as np
from scipy import signal

from author_event import author
from event_authoring.contour_joint_response import fit
from event_authoring.contour_response import QuadraticResponse
from event_authoring.measure import observe
from event_authoring.model import synth
from event_authoring.native import Renderer
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, out/'executed_verification.py')
    repo = Path(__file__).resolve().parents[1]
    root = Path('E:/VehicleSoundLab/references/analysis')
    entry = deepcopy(load(root/'A_exterior_startup_v1/crank1/profile.json')['parameters'])
    entry.update(gated=0, duration_seconds=.6, attack_seconds=.001, level=.7)
    entry.pop('contours',None)
    entry['modes'] = [dict(hz=hz,end_hz=hz,amplitude=amp,phase=phase,decay_seconds=1.)
        for hz,amp,phase in [(180.,.22,.3),(650.,.12,1.2)]]
    for band in entry['bands']:
        band.update(amplitude=0.,attack_seconds=0.,decay_seconds=1.)
    truth = deepcopy(entry)
    truth['contours'] = [dict(low_hz=lo,high_hz=hi,seconds=[0.,.06,.14,.24,.34,.46,.6],gain=gain)
        for lo,hi,gain in [(60.,300.,[.05,.3,1.,.08,.8,.4,.02]),
                          (300.,1200.,[.03,.7,.5,.1,.9,.2,.01])]]
    t=np.arange(28800)/48000
    background=.004*np.sin(2*np.pi*3100*t)+.001*np.sin(2*np.pi*7300*t+.2)
    known=synth(truth,seconds=.6)+background
    original=np.column_stack((known,-known))
    noise=np.column_stack((background,-background))
    _,arrays=observe(original,noise)
    fitted,report,response=fit(entry,original,noise,arrays)
    assert report['qualified'] and response['qualified'],report
    chosen=report['attempts'][report['selected_attempt']]
    assert all(a<b*.5 for a,b in zip(chosen['shape_rmse'],report['baseline_shape_rmse']))
    renderer=Renderer(repo)
    c,meta=renderer.render(fitted,'catch',dict(seconds=1.,seed=27431))
    py=np.pad(synth(fitted,seconds=1.),(0,len(c)-28800))
    c_error=float(np.max(abs(c-py)))
    assert c_error<3e-7
    # Keep a noncontoured modal/noise contribution to verify the affine term,
    # with coloration after envelope multiplication, rather than only tones.
    affine=deepcopy(truth)
    affine['contours']=affine['contours'][:1]
    for band in affine['bands']:
        band['amplitude']=.03
    affine['noise_lowpass_hz']=10000.
    basis=QuadraticResponse(affine,.6)
    assert np.mean(basis.constant**2)>1e-6
    gains=np.linspace(.1,1.3,basis.count)
    direct=deepcopy(affine)
    direct['contours'][0]['gain']=gains.tolist()
    wave=synth(direct,seconds=.6)
    waveform_error=float(np.max(abs(wave-basis.waveform(gains))))
    assert waveform_error<2e-14
    measurements={}
    for name,hop,edges,gram in [('temporal',240,((60,300),(300,1200),(1200,4500),(4500,14000)),basis.temporal),
        ('spectral',1024,((0,60),(60,300),(300,1200),(1200,4500),(4500,14000),(14000,24001)),basis.spectral)]:
        f,times,power=signal.spectrogram(wave,48000,window='hann',nperseg=2048,
            noverlap=2048-hop,detrend=False,scaling='density',mode='psd')
        observed=np.array([power[(f>=lo)&(f<hi)].sum(axis=0)*(f[1]-f[0]) for lo,hi in edges])
        if name=='spectral':observed=observed.mean(axis=1)
        predicted=basis.power(gram,gains)
        np.testing.assert_allclose(predicted,observed,rtol=3e-11,atol=3e-15)
        direction=np.linspace(-.3,.4,basis.count)
        eps=1e-5
        numeric=(basis.power(gram,gains+eps*direction)-basis.power(gram,gains-eps*direction))/(2*eps)
        analytic=np.einsum('...i,i->...',basis.derivative(gram,gains),direction)
        np.testing.assert_allclose(numeric,analytic,rtol=2e-6,atol=2e-10)
        measurements[name]=dict(power_max_error=float(np.max(abs(predicted-observed))),
            directional_derivative_max_error=float(np.max(abs(numeric-analytic))))
    legacy_results={}
    for name,folder in [('source_response',root/'startup_timbre_v1/crank1'),
                        ('four_band',root/'event_full_envelope_v1/verification1/candidate/analysis')]:
        # The explicit source job bound to the previously exported parameters.
        old=load(folder/'profile.json')
        job=out/(name+'.job.json')
        save(job,old['source_job'])
        author(job,out/name)
        new=load(out/name/'profile.json')
        assert new['parameters']==old['parameters']
        legacy_results[name]=dict(parameters_exact=True,source_job_exact=new['source_job']==old['source_job'])
    bindings=load(root/'A_exterior_startup_v1/selection1/runtime.json')
    assert len(bindings)==459 and all(sha(repo/name)==digest for name,digest in bindings.items())
    save(out/'report.json',dict(result='passed',known=report,known_C_python_max_error_FS=c_error,
        affine_waveform_max_error_FS=waveform_error,quadratic=measurements,legacy=legacy_results,
        runtime_voice_files_unchanged=459,timbre_accepted=False,goal_complete=False))
    print('known source, affine power/Jacobian and legacy parameters passed',flush=True)


if __name__=='__main__':
    main()
