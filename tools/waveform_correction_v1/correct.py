"""Fixed same-objective correction using the original metric and complete adjoint."""
import numpy as np


def refine(forward,adjoint,prior,metric_action,base,inverse,steps=2,initial_delta=None):
    if steps!=2:raise ValueError('This declared experiment requires exactly two correction steps')
    vector=np.asarray(base['z']).ndim==1
    def columns(x):
        x=np.asarray(x,float)
        return x[:,None] if x.ndim==1 else x
    z=columns(base['z']).copy();wave=columns(base['wave_model_residual']).copy()
    if initial_delta is not None:
        delta=columns(initial_delta)
        if delta.shape!=z.shape:raise ValueError('Initial perturbation shape differs')
        qdelta=prior.inverse_transpose(delta)
        wave+=np.column_stack([forward(v) for v in qdelta.T]);z+=delta
    history_z=[];history_wave=[];history_g=[];updates=[]
    for step in range(steps+1):
        weighted=metric_action(wave)
        g=np.column_stack([prior.inverse(adjoint(v)) for v in weighted.T])+z
        if not np.isfinite(g).all():raise ArithmeticError('Nonfinite original complete normal')
        history_z.append(z.copy());history_wave.append(wave.copy());history_g.append(g.copy())
        if step==steps:break
        delta=-inverse.apply(g)
        qdelta=prior.inverse_transpose(delta)
        wave+=np.column_stack([forward(v) for v in qdelta.T]);z+=delta;updates.append(delta)
    q=prior.inverse_transpose(z)
    def packed(x):return x[:,0] if vector else x
    return dict(q=packed(q),z=packed(z),wave_model_residual=packed(wave),
        original_normal=packed(history_g[-1]),history_z=np.array(history_z),
        history_wave=np.array(history_wave),history_original_normal=np.array(history_g),
        delta_z=np.array(updates))
