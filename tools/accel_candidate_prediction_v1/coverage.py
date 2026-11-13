"""Descriptive mixed-recording coverage; never a physical source budget."""
import numpy as np
from scipy import signal


def powers(audio,bands):
    n=len(audio);window=.5-.5*np.cos(2*np.pi*np.arange(n)/n)
    hz=np.fft.rfftfreq(n,1/48000)
    cells=abs(np.fft.rfft(audio*window[:,None],axis=0))**2/(n*np.sum(window*window))
    cells[1:-1]*=2
    result=np.array([cells[(hz>=lo)&(hz<hi)].sum(axis=0) for lo,hi in bands])
    freq,density=signal.periodogram(audio,fs=48000,window='hann',detrend=False,
                                    return_onesided=True,scaling='density',axis=0)
    independent=np.array([density[(freq>=lo)&(freq<hi)].sum(axis=0)*48000/n for lo,hi in bands])
    error=float(abs(result-independent).max());assert error<1e-12
    parseval_error=float(abs(cells.sum(axis=0)-np.sum((audio*window[:,None])**2,axis=0)/np.sum(window*window)).max())
    assert parseval_error<1e-12
    return result,dict(maximum_band_power_error=error,maximum_Parseval_error=parseval_error)


def known_controls(bands):
    n=12000;t=np.arange(n)/48000
    frequencies=[76,400,2000,5000,10000];amplitude=np.array([.2,.1,.03,.02,.01])
    left=sum(amp*np.cos(2*np.pi*f*t+.3*j) for j,(amp,f) in enumerate(zip(amplitude,frequencies)))
    x=np.column_stack((left,.67*left));actual,check=powers(x,bands)
    expected=.5*amplitude[:,None]**2*np.array([[1.,.67**2]])
    error=float(abs(actual-expected).max());assert error<1e-13
    return dict(analytic_grid_tone_power_error=error,**check)


def describe(folder,rows,inventories,bands):
    result=[];max_band=0.;max_parseval=0.
    for i,row in enumerate(rows):
        z=np.load(folder/f'native_{i:02d}.npz')
        source,first=powers(z['audio'],bands);residual,second=powers(z['residual'],bands)
        assert np.all(source>0)
        original=np.array(inventories[i]['bin'])*4
        result.append(dict(window=i,optimizer_success=row['success'],source_power_LR=source.tolist(),
            residual_power_LR=residual.tolist(),residual_source_ratio_LR=(residual/source).tolist(),
            original_peak_counts=[int(np.sum((original>=lo)&(original<hi))) for lo,hi in bands],
            fitted_center_counts=[sum(lo<=v['frequency_hz']<hi for v in row['lines']) for lo,hi in bands],
            eligible_center_counts=[sum(lo<=v['frequency_hz']<hi and v['eligible'] for v in row['lines']) for lo,hi in bands]))
        max_band=max(max_band,first['maximum_band_power_error'],second['maximum_band_power_error'])
        max_parseval=max(max_parseval,first['maximum_Parseval_error'],second['maximum_Parseval_error'])
    return dict(rows=result,median_residual_source_ratio_LR=np.median([v['residual_source_ratio_LR'] for v in result],axis=0).tolist(),
                maximum_band_power_error=max_band,maximum_Parseval_error=max_parseval,
                physical_source_separation=False,all_failed_windows_included=True)
