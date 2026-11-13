"""Known dense lines and explicit counterexamples before real acceleration fits."""
import numpy as np
from line_motion_v1.local_chirps import evaluate
from .fit import fit


def controls(plan):
    rate=plan['sample_rate'];n=plan['frames'];t=np.arange(n)/rate-n/(2*rate)
    orders=np.arange(5,31);moving=60.613*orders*(1+.05*.125);fixed=np.array([387.23,947.61,1421.17,2051.31])
    frequencies=np.r_[moving,fixed];q=np.r_[60.613*orders*.05,np.zeros(4)]
    amplitude=np.r_[.12*(orders/5)**-.5,np.full(4,.05)]
    phase=np.arange(len(q))*.173;sort=np.argsort(frequencies)
    frequencies,q,amplitude,phase=[v[sort] for v in [frequencies,q,amplitude,phase]]
    def wave(frequencies=frequencies,q=q,amplitude=amplitude):
        angle=2*np.pi*(t[:,None]*frequencies+.5*t[:,None]**2*q)
        return np.column_stack((np.cos(angle+phase)@amplitude,np.cos(angle+phase+.37)@(amplitude*.67)))
    audio=wave();df=rate/n;nominal=np.round(frequencies/df)*df
    report={};fixtures={}
    def run(name,x,nominal=nominal,initial=None):
        result,arrays=fit(x,nominal,np.zeros(len(nominal)) if initial is None else initial,plan)
        report[name]=result;fixtures[name]=dict(audio=x,**arrays);return result
    base=run('dense_moving_and_fixed',audio)
    assert base['success'] and all(row['eligible'] for row in base['lines']),base
    error_f=max(abs(row['frequency_hz']-f) for row,f in zip(base['lines'],frequencies))
    error_q=max(abs(row['chirp_hz_per_second']-v) for row,v in zip(base['lines'],q))
    error_a=max(np.max(abs(np.array(row['amplitude_LR'])-a*np.array([1,.67]))) for row,a in zip(base['lines'],amplitude))
    assert error_f<1e-5 and error_q<1e-4 and error_a<1e-7,(error_f,error_q,error_a)
    report['analytic_truth']=dict(frequencies=frequencies.tolist(),chirps=q.tolist(),amplitudes=amplitude.tolist(),
        phases=phase.tolist(),maximum_frequency_error=error_f,maximum_chirp_error=error_q,maximum_amplitude_error=error_a)
    gain=run('global_gain',audio*.13)
    assert gain['success'] and all(row['eligible'] for row in gain['lines'])
    assert max(abs(row['frequency_hz']-f) for row,f in zip(gain['lines'],frequencies))<1e-5
    # Missing target and separately modeled neighbour, not a substituted target.
    lost=12;extra=frequencies[lost]+24.7
    angle=2*np.pi*(frequencies[lost]*t+.5*q[lost]*t*t)
    missing=audio-np.column_stack((amplitude[lost]*np.cos(angle+phase[lost]),amplitude[lost]*.67*np.cos(angle+phase[lost]+.37)))
    neighbour=.07*np.cos(2*np.pi*extra*t+.4);missing+=np.column_stack((neighbour,.67*neighbour))
    expanded=np.sort(np.r_[nominal,round(extra/df)*df]);result=run('missing_with_neighbour',missing,expanded)
    target=next(row for row in result['lines'] if row['nominal_hz']==nominal[lost]);assert not target['eligible'],target
    # Check analytic derivatives on a small independent parameter vector.
    nominal_j=np.array([357.,1193.]);p=np.array([.3,-.4,23.,-31.,.12,.07,-.08,.03,.001])
    time=t[::71];_,jac=evaluate(p,nominal_j,time);maximum=0
    for k in range(len(p)):
        step=1e-5 if k<4 else 1e-6;plus=p.copy();minus=p.copy();plus[k]+=step;minus[k]-=step
        numeric=(evaluate(plus,nominal_j,time)[0]-evaluate(minus,nominal_j,time)[0])/(2*step)
        maximum=max(maximum,float(abs(numeric-jac[:,k]).max()))
    assert maximum<1e-8,maximum;report['jacobian_error']=maximum
    rng=np.random.default_rng(761233);left=rng.normal(0,.1,n);right=rng.normal(0,.1,n)
    noise_nominal=nominal[::5]
    run('same_mono_noise',np.column_stack((left,.67*left)),noise_nominal)
    run('independent_stereo_noise',np.column_stack((left,right)),noise_nominal)
    nonlinear=.2*np.cos(2*np.pi*(811.31*t+15*t*t+(2000/6)*t**3)+.2)
    run('nonlinear_FM_mismatch',np.column_stack((nonlinear,.67*nonlinear)),np.array([812.]))
    report['interpretation']='Exact linear chirps are known controls; noise/mismatch fitted eligibility does not identify physical tones or phase continuity.'
    return report,fixtures
