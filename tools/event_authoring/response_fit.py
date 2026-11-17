"""Optional full-spectrum gain fit using the unchanged finite event generator."""
from copy import deepcopy
import numpy as np
from scipy import optimize,signal

from .contract import validate
from .model import synth
from .measure import spectrum

EDGES=((0,60),(60,300),(300,1200),(1200,4500),(4500,14000),(14000,24001))


def calibrate(profile,arrays,duration):
    """Fit <=16 fixed modal/noise amplitudes; do not invent spectral components."""
    f,power,background,_,_,_,_=arrays
    df=f[1]-f[0]
    excess=np.maximum(0,power-background)
    targets=np.array([excess[(f>=lo)&(f<hi)].sum()*df for lo,hi in EDGES])
    total=float(targets.sum())
    if total<=1e-20:
        raise ValueError('No positive spectral excess for response fitting')
    members=[];waves=[]
    for category in ('modes','bands'):
        for i,row in enumerate(profile[category]):
            if row['amplitude']<=0:continue
            basis=deepcopy(profile);basis['level']=1.
            for key in ('modes','bands'):
                for j,item in enumerate(basis[key]):
                    if key!=category or j!=i:item['amplitude']=0.
            wave=synth(basis,seconds=duration)
            if np.mean(wave*wave)>1e-30:
                members.append((category,i));waves.append(wave)
    if not waves:raise ValueError('No nonzero event response basis')
    waves=np.column_stack(waves);count=len(members)
    gram=np.zeros((len(EDGES),count,count))
    for i in range(count):
        for j in range(i,count):
            frequency,cross=signal.csd(waves[:,i],waves[:,j],48000,nperseg=min(2048,len(waves)),detrend=False)
            for k,(lo,hi) in enumerate(EDGES):
                use=(frequency>=lo)&(frequency<hi)
                gram[k,i,j]=gram[k,j,i]=float(cross[use].real.sum()*(frequency[1]-frequency[0]))
    floor=total*1e-6
    scale=np.maximum(targets,total*1e-4)
    diagonal=np.diagonal(gram,axis1=1,axis2=2)
    initial,_=optimize.nnls(diagonal/scale[:,None],targets/scale,maxiter=400)
    initial=np.clip(np.sqrt(initial),1e-6,63.)
    def residual(gain):
        generated=np.einsum('i,bij,j->b',gain,gram,gain)
        return np.log(np.maximum(generated,0)+floor)-np.log(targets+floor)
    def jacobian(gain):
        generated=np.einsum('i,bij,j->b',gain,gram,gain)
        return 2*np.einsum('bij,j->bi',gram,gain)/(np.maximum(generated,0)+floor)[:,None]
    result=optimize.least_squares(residual,initial,jac=jacobian,bounds=(0,64),
        max_nfev=240,ftol=1e-10,xtol=1e-10,gtol=1e-10)
    fitted=deepcopy(profile);fitted['level']=1.
    for gain,(category,i) in zip(result.x,members):
        fitted[category][i]['amplitude']*=float(gain)
    level=max([1.]+[m['amplitude']/4 for m in fitted['modes']]+[b['amplitude']/8 for b in fitted['bands']])
    contract_fits=level<=8
    fitted['level']=min(8.,level)
    for category in ('modes','bands'):
        for row in fitted[category]:row['amplitude']/=level
    validate(fitted)
    wave=synth(fitted,seconds=duration);frequency,actual=spectrum(wave[:,None]);rows=[]
    for (lo,hi),target in zip(EDGES,targets):
        generated=float(actual[(frequency>=lo)&(frequency<hi)].sum()*(frequency[1]-frequency[0]))
        error=float(10*np.log10(max(generated,1e-30)/max(target,1e-30)))
        significant=bool(target>=total*1e-4)
        passed=abs(error)<=3 if significant else generated<=max(target*2,total*2e-4)
        rows.append(dict(hz=[lo,hi],target_power=float(target),generated_power=generated,
                         error_db=error,significant_target=significant,passed=bool(passed)))
    return fitted,dict(method='finite-response-gains-v1',qualified=bool(contract_fits and all(r['passed'] for r in rows)),
        bands=rows,groups=count,evaluations=result.nfev,optimizer_terminated=bool(result.success),
        amplitude_contract_fits=contract_fits,seed=27431,target_positive_psd_excess_power=total,
        policy='Six bands including below60Hz and above14kHz; nonnegative gains for each existing mode/SOS; exact finite-waveform cross-power, <=16 gains, max240 evaluations.',
        limitations='No frequency/envelope/phase/room change or recorded waveform playback. Statistical excess, one fit seed and band agreement do not establish source isolation, mechanical identity, transients or timbre acceptance.')


def search(profile,arrays,duration):
    """Select a source-noise lowpass and component gains within a fixed small grid."""
    attempts=[];candidates=[]
    for cutoff in (0.,4000.,6000.,8000.,10000.,14000.):
        candidate=deepcopy(profile)
        if cutoff:candidate['noise_lowpass_hz']=cutoff
        else:candidate.pop('noise_lowpass_hz',None)
        fitted,report=calibrate(candidate,arrays,duration)
        score=float(sum((np.log(max(r['generated_power'],1e-30)+report['target_positive_psd_excess_power']*1e-6)-
                         np.log(r['target_power']+report['target_positive_psd_excess_power']*1e-6))**2 for r in report['bands']))
        attempts.append(dict(noise_lowpass_hz=cutoff,score=score,qualified=report['qualified'],
                             bands=report['bands'],evaluations=report['evaluations']))
        candidates.append((not report['qualified'],score,fitted,report))
    _,_,fitted,report=min(candidates,key=lambda row:(row[0],row[1]))
    report.update(method='source-response-v1',noise_lowpass_hz=fitted.get('noise_lowpass_hz',0.),attempts=attempts,
                  limitations='Only procedural noise receives the optional fourth-order lowpass; modal phases/frequencies and envelopes stay unchanged. Six fixed cutoff choices and <=240 evaluations each. Positive PSD excess is an acoustic target, not source separation, RPM or timbre acceptance.')
    return fitted,report
