"""Signed coefficient cross-moment identities, not physical source separation."""
import numpy as np


def measure(amplitude, phase):
    turn = np.exp(1j*(phase[..., 0]-phase[..., 1]))
    product = amplitude[..., 0]*amplitude[..., 1]
    mean_product = product.mean(axis=0)
    moment = turn.mean(axis=0)
    cross = (product*turn).mean(axis=0)
    return dict(second=(amplitude**2).mean(axis=0), product=mean_product,
                phase_moment=moment, association=cross-mean_product*moment,
                cross=cross)


def marginal_moment(table):
    """Exact integral of exp(i*linear phase quantile), constant half-cell tails."""
    a, b = table[:-1], table[1:]
    interior = np.exp(.5j*(a+b))*np.sinc((b-a)/(2*np.pi))
    return (.5*np.exp(1j*table[0])+.5*np.exp(1j*table[-1])+interior.sum(axis=0))/len(table)


def decompose(source, model, indices, phase_integral=None, model_denominators=None):
    output = {key: [] for key in ['source_coherence','model_coherence','error',
              'amplitude_product','phase_marginal','association','denominator',
              'phase_quantile_bias','phase_QMC_discrepancy']}
    for group, mask in enumerate(indices):
        ds = np.sqrt(source['second'][mask].sum(axis=0).prod())
        dm = (np.sqrt(model['second'][mask].sum(axis=0).prod())
              if model_denominators is None else model_denominators[group])
        if ds <= 0 or dm <= 0:
            raise ValueError('Stereo coherence is undefined for a silent channel/band')
        cs = source['cross'][mask].sum(); cm = model['cross'][mask].sum()
        product = np.sum((model['product'][mask]-source['product'][mask])*source['phase_moment'][mask])/ds
        phase = np.sum(model['product'][mask]*(model['phase_moment'][mask]-source['phase_moment'][mask]))/ds
        association = np.sum(model['association'][mask]-source['association'][mask])/ds
        denominator = cm*(1/dm-1/ds)
        if phase_integral is None:
            quantile_bias = phase; QMC = 0j
        else:
            quantile_bias = np.sum(model['product'][mask]*(phase_integral[mask]-source['phase_moment'][mask]))/ds
            QMC = np.sum(model['product'][mask]*(model['phase_moment'][mask]-phase_integral[mask]))/ds
        for key, value in dict(source_coherence=cs/ds,model_coherence=cm/dm,error=cm/dm-cs/ds,
            amplitude_product=product,phase_marginal=phase,association=association,denominator=denominator,
            phase_quantile_bias=quantile_bias,phase_QMC_discrepancy=QMC).items():
            output[key].append(value)
    return {key:np.array(value) for key,value in output.items()}
