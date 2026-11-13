"""Compile immutable acoustic parameters; evidence remains outside the profile."""
import copy
import numpy as np
from idle_modal_v1 import modal
from idle_material_v1.features import observe
from idle_texture_v2 import spectral,dynamics


def band_power(audio,recipe):
    return np.asarray(observe(audio,recipe['energy_bands_hz'])['mean_power'])


def compile_profile(reference,recipe,modal_recipe,frames,*,preserved_modal=None):
    if reference.ndim!=2 or reference.shape[1]!=2 or not np.isfinite(reference).all():
        raise ValueError('Expected finite stereo training samples')
    if recipe['sample_rate']!=48000 or len(reference)<modal_recipe['analysis_frames']:
        raise ValueError('Unsupported rate or insufficient training samples')
    evidence={}
    if preserved_modal is None:
        model=modal.fit(reference,48000,modal_recipe)
        evidence['modal']=model.pop('evidence')
    else:model=copy.deepcopy(preserved_modal)
    main=modal.render(model,frames,48000)
    target=band_power(reference,recipe);initial=band_power(main,recipe)
    if preserved_modal is None:
        ceiling=modal_recipe['modal_power_ceiling_fraction']
        scale=min(1.,float(np.sqrt(np.min(ceiling*target/np.maximum(initial,1e-30)))))
        model['amplitude_LR']=(np.asarray(model['amplitude_LR'])*scale).tolist()
        main*=scale;evidence['modal_ceiling_scale']=scale
    mainpower=band_power(main,recipe)
    filters,budget=spectral.fit(reference,target,mainpower,recipe)
    envelope=dynamics.fit(reference,recipe)
    evidence['envelope']=envelope.pop('evidence')
    profile=dict(schema='vsl.fixed-source-study/1',sample_rate=48000,modal=model,
        kernels=filters,envelope=envelope,warmup_frames=recipe['warmup_frames'],
        recorded_trajectory=False,room=False,RPM=None,
        scope='Independent fixed-context sound; not shared-phase DNA, calibrated RPM or full stereo residual')
    evidence.update(training_power_LR=target.tolist(),modal_power_LR=mainpower.tolist(),budget=budget)
    return profile,evidence
