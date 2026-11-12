"""Only weak, bidirectionally supported low-speed power shapes are enabled."""
import numpy as np
from dna_texture_v2.observe import analytic_band,envelope
from resonant_detail_v1.envelope import samples

def fit(reference,root,plan):
    metric=dict(plan,acoustic_cycle_frames=48000/root,filter_taps=2049,edge_discard_frames=4096)
    models=[]
    for band in plan['bands_hz']:
        beta=np.zeros(2*plan['envelope_fourier_orders']);rows=[]
        # The existing normalized reference is antialiased above the low
        # anchor's source bandwidth. Do not fit its missing upper texture.
        if band[1]<=3000:
            rows=envelope(analytic_band(reference,band,metric),metric)
            if all(v['heldout_improvement'] is not None and v['heldout_improvement']>=plan['minimum_envelope_half_validation_improvement'] for v in rows):
                candidate=np.mean([v['coefficients'] for v in rows],axis=0)
                phase=2*np.pi*np.arange(4096)/4096
                order=np.arange(1,plan['envelope_fourier_orders']+1)
                design=np.column_stack((np.cos(phase[:,None]*order),np.sin(phase[:,None]*order)))
                power=1+design@candidate
                if min(power)>=.05 and max(abs(power-1))<=plan['maximum_periodic_power_deviation']:beta=candidate
        models.append(dict(coefficients=beta.tolist(),enabled=bool(np.any(beta)),band_hz=band,
            half_validation=rows,not_physical_firing_model=True))
    return models
