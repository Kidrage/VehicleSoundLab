"""Independent scalar-signal, native-peak and neighbour-initialization oracles."""
import math
import numpy as np
from scipy.fft import rfft,irfft,rfftfreq
from native_chirp_audit_v1.wave import near


def signal(case,p):
    t=np.arange(p['frames']*p['windows'])/p['sample_rate']
    if case=='bandlimited_mono_noise':
        raw=np.random.default_rng(p['noise']['seed']).normal(size=len(t))
        z=rfft(raw)
        hz=rfftfreq(len(t),1/p['sample_rate'])
        lo,hi=p['noise']['band_hz']
        z[(hz<lo)|(hz>=hi)]=0
        left=irfft(z,n=len(t))
        left*=p['noise']['rms']/math.sqrt(math.fsum(left*left)/len(t))
        return np.stack([left,left*p['noise']['right_gain']],axis=1)
    am=case in ['am_only','am_fm']
    fm=case in ['fm_only','am_fm']
    z=np.zeros((len(t),2),dtype=complex)
    for k,base in enumerate(p['base_hz']):
        q=base*p['moving'][k]*p['linear_slope_per_second']
        omega=math.tau*p['FM']['modulation_hz']
        deviation=(base/p['FM']['reference_hz'])*p['FM']['deviation_at_reference_hz']*fm*p['moving'][k]
        theta=math.tau*base*t+math.pi*q*t*t-math.tau*deviation/omega*np.cos(omega*t)+p['phase_radians'][k]
        carrier=np.exp(1j*theta)*p['amplitude_L'][k]
        z[:,0]+=carrier
        z[:,1]+=carrier*complex(math.cos(p['right_phase_radians']),math.sin(p['right_phase_radians']))*p['right_gain']
    gain=1+p['AM']['depth']*am*np.sin(math.tau*p['AM']['frequency_hz']*t)
    return z.real*gain[:,None]


def truth_rows(case,p,rows):
    if case=='bandlimited_mono_noise':
        assert rows==[]
        return
    assert len(rows)==p['windows']
    for i,row in enumerate(rows):
        center=(i+.5)*p['frames']/p['sample_rate']
        assert len(row['lines'])==len(p['base_hz']) and row['diagnostic_only'] and row['success']
        for k,line in enumerate(row['lines']):
            base=p['base_hz'][k]
            q=base*p['moving'][k]*p['linear_slope_per_second']
            omega=math.tau*p['FM']['modulation_hz']
            dev=(base/p['FM']['reference_hz'])*p['FM']['deviation_at_reference_hz']*p['moving'][k]*(case in ['fm_only','am_fm'])
            near(line['frequency_hz'],base+q*center+dev*math.sin(omega*center))
            near(line['chirp_hz_per_second'],q+dev*omega*math.cos(omega*center))
            phase=math.tau*(base*center+.5*q*center**2-dev/omega*math.cos(omega*center))+p['phase_radians'][k]
            near(line['phase_at_midpoint_LR'],[phase,phase+p['right_phase_radians']])
            gain=1+p['AM']['depth']*(case in ['am_only','am_fm'])*math.sin(math.tau*p['AM']['frequency_hz']*center)
            amp=p['amplitude_L'][k]*gain
            near(line['amplitude_LR'],[amp,amp*p['right_gain']])
            assert line['index']==k and line['eligible']


def inventory(audio,actual,rp):
    n=len(audio)
    w=np.hanning(n+1)[:-1]
    z=rfft(audio*w[:,None],axis=0)
    power=(z.real*z.real+z.imag*z.imag)*2/(n*math.fsum(w*w))
    power[[0,-1]]*=.5
    total=power.sum(axis=1)
    log=10*np.log10(np.maximum(total,np.finfo(float).tiny))
    # At 4Hz/native cell the original 6Hz spacing rounds to 2 cells. Strict
    # local maxima are already at least 2 cells apart; no distance suppression.
    assert round(rp['peak_spacing_hz']/4)==2
    assert not np.any(log[1:]==log[:-1]),'Plateau needs separate original-rule audit'
    peaks=np.flatnonzero((log[1:-1]>log[:-2])&(log[1:-1]>log[2:]))+1
    bins=[]
    freqs=[]
    for lo,hi in [[30,200],[200,7000]]:
        maximum=max(total[j] for j in range(len(total)) if lo<=j*4<hi)
        for j in peaks:
            if not lo<=j*4<hi or total[j]<maximum*10**(rp['peak_floor_db_relative_to_maximum']/10):continue
            minima=[]
            for direction in [-1,1]:
                at=j
                lowest=log[j]
                while 0<=at<len(log) and log[at]<=log[j]:
                    lowest=min(lowest,log[at])
                    at+=direction
                minima.append(lowest)
            prominence=log[j]-max(minima)
            if prominence<rp['peak_prominence_db']:continue
            d=.5*(log[j-1]-log[j+1])/(log[j-1]-2*log[j]+log[j+1])
            bins.append(int(j))
            freqs.append((j+max(-.5,min(.5,d)))*4)
    assert bins==actual['bin'],(bins,actual['bin'])
    error=near(freqs,actual['hz'],1e-8)
    strongest=int(np.argmax([total[j] for j in bins]))
    return dict(error=error,strongest_index=strongest,strongest_hz=freqs[strongest])


def initialization(invs,ratios,actual):
    for i,(inv,init) in enumerate(zip(invs,actual)):
        adjacent=[j for j in [i-1,i+1] if 0<=j<len(invs)]
        assert sorted(map(int,init['neighbor_graphs']))==adjacent
        graphs={}
        for j in adjacent:
            ratio=ratios[j]/ratios[i]
            centers=[f*ratio for f in inv['hz']]
            radii=[4*(1+ratio)+f*(2**(.5/192)-1) for f in centers]
            edges=[[int(abs(f-g)<=r) for g in invs[j]['hz']] for f,r in zip(centers,radii)]
            graph=init['neighbor_graphs'][str(j)]
            assert graph['edges']==edges
            near(centers,graph['expected_hz'])
            near(radii,graph['radius_hz'])
            for k,edge in enumerate(edges):
                picks=[v for v,yes in enumerate(edge) if yes]
                unique=len(picks)==1 and sum(row[picks[0]] for row in edges)==1
                assert graph['state'][k]==('unique' if unique else 'ambiguous' if picks else 'absent')
                assert graph['chosen'][k]==(picks[0] if unique else None)
            graphs[j]=graph
        for k in range(len(inv['hz'])):
            avail=[j for j in adjacent if graphs[j]['state'][k]=='unique']
            def frequency(j):return invs[j]['hz'][graphs[j]['chosen'][k]]
            q=(frequency(i+1)-frequency(i-1))/.5 if len(avail)==2 else (frequency(avail[0])-inv['hz'][k])/((avail[0]-i)*.25) if avail else 0
            near(q,init['initial_chirp'][k])
