"""Fixed-offset linear sideband observations conditional on an external phase coordinate."""
import numpy as np

OFFSET_HZ=3.


def design(frequency,chirp,time):
    phase=2*np.pi*(time[:,None]*frequency+.5*time[:,None]**2*chirp)
    angles=phase[:,:,None]+2*np.pi*time[:,None,None]*np.array([0.,OFFSET_HZ,-OFFSET_HZ])
    flat=angles.reshape(len(time),-1)
    return np.column_stack((np.cos(flat),np.sin(flat),np.ones(len(time))))


def complex_pair(z):return [float(z.real),float(z.imag)]


def parity(central,upper,lower):
    # Numerators remain observable even if a normalized phase reference is undefined.
    ac=(upper*np.conj(central)+np.conj(lower)*central)/2
    pc=(upper*np.conj(central)-np.conj(lower)*central)/(2j)
    power=float(abs(central)**2)
    return dict(central=complex_pair(central),upper=complex_pair(upper),lower=complex_pair(lower),
        central_power=power,am_cross=complex_pair(ac),quadrature_cross=complex_pair(pc),
        am_relative=None if power==0 else complex_pair(ac/power),
        quadrature_relative=None if power==0 else complex_pair(pc/power),
        normalization='Conditional on nonzero fitted carrier; carrier reliability and physical source not established')


def observe(audio,frequency,chirp,time):
    matrix=design(frequency,chirp,time);m=len(frequency);n=len(time)
    weight=np.cos(np.pi*time)/np.sqrt(n)
    coefficients,residuals,rank,singular=np.linalg.lstsq(weight[:,None]*matrix,weight*audio,rcond=None)
    fitted=matrix@coefficients;residual=fitted-audio;gradient=matrix.T@(weight**2*residual)
    z=coefficients[:3*m].reshape(m,3)-1j*coefficients[3*m:6*m].reshape(m,3)
    details=dict(coefficients=coefficients.tolist(),complex_components=[[complex_pair(v) for v in row] for row in z],
        parity=[parity(*row) for row in z],cost=float(.5*np.dot(weight**2,residual**2)),
        gradient_infinity=float(abs(gradient).max()),rank=int(rank),columns=matrix.shape[1],
        singular_values=singular.tolist(),condition=float(singular[0]/singular[-1]),
        frequency_Hz=frequency.tolist(),chirp_Hz_per_s=chirp.tolist(),offset_Hz=OFFSET_HZ,
        phase_coordinate_qualified=False,physical_source_classified=False)
    return fitted,details
