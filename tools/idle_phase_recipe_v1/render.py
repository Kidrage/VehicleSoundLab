"""Paired optional idle voices. Phase motion, modal DNA and resonant details stay separate."""
import numpy as np
from scipy import signal
from idle_modal_v1.modal import render as modal_render
from idle_phase_difference_v1.features import matrix
from idle_positive_power_v1.model import predict
from idle_phase_recipe_v1.phase import M, H, RIGHT, INDICES, coordinates, nodes, spline, phasors

MASK = (1 << 64)-1
BLOCK = 24000
METHODS = ['static', 'post', 'relation_q', 'relation_full']


def synthesis_frame(chart_model, source):
    """Lift circular charts to the SAME unwrapped phase branch as the carrier fit."""
    model = dict(chart_model)
    theta = np.unwrap(np.angle(source), axis=0)
    raw = theta@M.T
    w = coordinates(source)
    chart = np.angle(w*np.exp(-1j*np.asarray(model['coordinate_center'])))
    turn = np.rint(np.mean(raw-chart-np.asarray(model['coordinate_center']), axis=0)/(2*np.pi))
    lifted = np.asarray(model['coordinate_center'])+turn*2*np.pi
    error = float(abs(np.exp(1j*(raw-chart-lifted))-1).max())
    assert error < 1e-10
    reconstructed = (theta@H/(H@H))[:, None]*H+raw@RIGHT.T
    reconstruction_error = float(abs(reconstructed-theta).max()); assert reconstruction_error < 1e-10
    model.update(coordinate_center=lifted.tolist(), chart_branch_turns=turn.astype(int).tolist(),
                 carrier_branch_reconstruction_error_rad=reconstruction_error)
    return model


def free_phasors(profile, t):
    f = np.asarray(profile['modal']['frequencies_hz'])[INDICES]
    p = np.asarray(profile['modal']['initial_phase_LR'])[INDICES, 0]
    return np.exp(1j*(2*np.pi*np.remainder(t[:, None]*f, 1.)+p))


def phase_audio(profile, model, motion, frames, rate):
    old = modal_render(profile['modal'], frames, rate); new = old.copy()
    amplitude = np.asarray(profile['modal']['amplitude_LR'])[INDICES]
    phase = np.asarray(profile['modal']['initial_phase_LR'])[INDICES]
    delta = phase[:, 1]-phase[:, 0]
    for start in range(0, frames, BLOCK):
        t = np.arange(start, min(frames,start+BLOCK))/rate
        z0, z1 = free_phasors(profile,t), phasors(model,motion,t)
        for c in range(2):
            rotation = np.exp(1j*delta*c)
            new[start:start+len(t),c] += ((z1-z0)*rotation).real@amplitude[:,c]
    return old,new


def noise(seed, index, count, kind):
    key = (seed ^ (0x9E3779B97F4A7C15*(index+1) & MASK))
    offsets = dict(gaussian=0x794323AA, normal=0xD1B54A32D192ED03, uniform=0x94D049BB133111EB)
    rng = np.random.Generator(np.random.PCG64(key ^ offsets[kind]))
    return rng.random(count) if kind=='uniform' else rng.standard_normal(count)


def render(profile, model, law, probability, seed, frames, rate=48000):
    # Extra future nodes make the observed prefix independent of spline end boundary.
    values = nodes(model,seed,frames/rate+2.)
    motion = spline(model,values)
    old,new = phase_audio(profile,model,motion,frames,rate)
    details = {name: np.zeros_like(old) for name in ['static','post','related']}
    count = frames+profile['warmup_frames']; warm = profile['warmup_frames']
    q_free = np.empty((frames//48,4)); q_related=np.empty_like(q_free)
    for start in range(0,frames,BLOCK):
        t=np.arange(start,min(frames,start+BLOCK))/rate
        q0=predict(law,matrix(free_phasors(profile,t),hop=1,trim=0))
        q1=predict(law,matrix(phasors(model,motion,t),hop=1,trim=0))
        for q in [q0,q1]:
            assert np.all(q.min(axis=0)>=law['bounds']['power_lower'])
            assert np.all(q.max(axis=0)<=law['bounds']['power_upper'])
        q_free[start//48:(start+len(t))//48]=q0.reshape(-1,48,4).mean(axis=1)
        q_related[start//48:(start+len(t))//48]=q1.reshape(-1,48,4).mean(axis=1)
    events=[]
    for index,kernel in enumerate(profile['kernels']):
        taps=np.asarray(kernel['taps']); gain=kernel['gain']; ratio=np.array([1.,kernel['right_over_left']])
        gaussian=noise(seed,index,count,'gaussian')
        y=signal.oaconvolve(gaussian,taps)[warm:count]*gain
        details['static'] += y[:,None]*ratio
        if index<2:
            details['post'] += y[:,None]*ratio;details['related'] += y[:,None]*ratio
        else:
            u=noise(seed,index,count,'uniform'); n=noise(seed,index,count,'normal');p=probability[index-2]
            sparse=np.where(u<p,n/np.sqrt(p),0.)
            y=signal.oaconvolve(sparse,taps)[warm:count]*gain
            events.append(dict(index=index,on=int((u<p).sum()),probability=float(p)))
            for start in range(0,frames,BLOCK):
                t=np.arange(start,min(frames,start+BLOCK))/rate
                q0=predict(law,matrix(free_phasors(profile,t),hop=1,trim=0))[:,index-2]
                q1=predict(law,matrix(phasors(model,motion,t),hop=1,trim=0))[:,index-2]
                segment=y[start:start+len(t),None]*ratio
                details['post'][start:start+len(t)] += segment*np.sqrt(q0[:,None])
                details['related'][start:start+len(t)] += segment*np.sqrt(q1[:,None])
    return dict(old_main=old,new_main=new,static_detail=details['static'],post_detail=details['post'],
        related_detail=details['related'],static=old+details['static'],post=old+details['post'],
        relation_q=old+details['related'],relation_full=new+details['related']), dict(
        coordinate_nodes=values,q_free=q_free,q_related=q_related,events=events)
