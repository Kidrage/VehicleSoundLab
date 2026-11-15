"""Restore original KNOWN fixtures and their complete unmodified objective."""
import numpy as np
from observer_representer_v1.fixtures import DenseFixture
from observer_complete_v1.synthesis import WaveSynthesis
from observer_supported_v1.metric import SupportedMetric
from observer_supported_v1.fit import SupportedSystem
from observer_representer_v1.primal import PenaltyPrimal
from observer_representer_v1.dual import representer_certificate
from observer_frequency_v1.optimality import bound
from observer_inverse_v1.fit import complex_array,real_vector
from waveform_structured_v1.penalty import TemporalPenalty
from waveform_stream_v1.shared import SharedSupportedGeometry


def restore(kind,case,base):
    audio,positions,orders,scale=(base[n] for n in ('audio','positions','orders','scale'))
    if case['kind']=='algebra':
        system=DenseFixture(audio.shape[1],float(scale[2,0]),case['label']=='silent_right')
        assert np.array_equal(system.audio,audio) and np.array_equal(system.scale,scale)
        if kind=='shared8':
            C=audio.shape[1];M,H,_=system.nshape
            P=system.Phi[::C,::C];W=system.wave_metric[::C,::C]
            prior=TemporalPenalty((M,H,1),system.D.toarray(),system.alpha,system.beta)
        else:
            P=system.Phi;W=system.wave_metric
            prior=TemporalPenalty(system.nshape,system.D.toarray(),system.alpha,system.beta)
        forward=lambda x:P@x;adjoint=lambda x:P.T@x;metric_action=lambda e:W@e
    else:
        synthesis=WaveSynthesis(len(audio),positions,orders,audio.shape[1])
        metric=SupportedMetric(audio,64.);system=SupportedSystem(synthesis,scale,metric)
        if kind=='shared8':
            geometry=SharedSupportedGeometry(system)
            prior,forward,adjoint=geometry.prior,geometry.forward,geometry.adjoint
        else:
            prior=TemporalPenalty(system.nshape,system.D.toarray(),system.alpha,system.beta)
            forward=lambda x:synthesis.synthesize(complex_array(x,system.nshape)*system.scale[None]).ravel()
            adjoint=lambda e:real_vector(synthesis.adjoint(e.reshape(audio.shape))*system.scale[None])
        def metric_action(e):
            if e.shape!=audio.shape:raise ValueError('Original mono/stereo metric dimensions differ')
            return e/metric.wave_scale**2+metric.adjoint(metric.forward(e))
    return system,prior,forward,adjoint,metric_action


def evaluate(system,audio,corrected,reference,kind):
    if system.nsize>512:raise ValueError('This complete known evaluator is not a full/source runner')
    q=corrected['q'].ravel();fitted=complex_array(q,system.nshape)*system.scale[None]
    rhs=system.rhs(audio);residual=system@q-rhs;u=-residual[:system.ysize]
    gradient=float(np.linalg.norm(system.rmatvec(residual))/max(np.linalg.norm(system.rmatvec(rhs)),1e-300))
    relative=float(np.linalg.norm(q-reference)/max(np.linalg.norm(reference),1e-300))
    primal=PenaltyPrimal(system)
    prior=TemporalPenalty(system.nshape,system.D.toarray(),system.alpha,system.beta)
    packed=prior.root_transpose(q)
    model_wave=corrected['wave_model_residual'].reshape(audio.shape)
    model=np.r_[system.rhs(model_wave)[:system.ysize],packed]
    normal=primal.rmatvec(model)
    norm_squared=0.;basis=np.zeros(system.nsize)
    for j in range(system.nsize):
        basis[j]=1.;col=primal@basis;norm_squared+=float(col@col);basis[j]=0.
    normA=np.sqrt(norm_squared)
    stable=float(np.linalg.norm(normal)/max(normA*np.linalg.norm(model),1e-300))
    full_rhs=np.r_[rhs[:system.ysize],np.zeros(system.nsize)]
    backward=float(np.linalg.norm(primal@packed-full_rhs-model)/max(np.linalg.norm(full_rhs),1e-300))
    rc,pc=bound(system,audio,fitted),representer_certificate(system,audio,fitted,u)
    qualified=bool(relative<2e-7 and gradient<2e-7 and stable<=1e-11 and backward<=1e-11
        and rc['additional_gap_gate_passed'] and pc['additional_gap_gate_passed'])
    return dict(q_interleaved=q,u=u,original_model_residual=model,original_model_normal=normal),dict(
        qualified=qualified,dense_relative_error=relative,original_gradient=gradient,
        stable_complete_normal=stable,original_backward=backward,original_root_Frobenius=float(normA),
        residual_certificate=rc,representer_certificate=pc,
        all_original_observations_and_directions_retained=True)
