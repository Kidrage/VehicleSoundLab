"""Optional finite-response fit across fixed procedural excitation realizations."""
from copy import deepcopy
import numpy as np
from scipy import optimize,signal

from .contract import validate
from .measure import spectrum
from .model import synth
from .response_fit import EDGES

TRAIN_SEEDS=(27431,1049,17467,28123)
HELD_OUT_SEEDS=(54123,5823,27183,48193)
CUTOFFS=(0.,4000.,6000.,8000.,10000.,14000.)


def target_powers(arrays):
    f,power,background,*_=arrays;positive=np.maximum(0,power-background);df=f[1]-f[0]
    return np.array([positive[(f>=lo)&(f<hi)].sum()*df for lo,hi in EDGES])


def band_powers(wave):
    hz,power=spectrum(np.asarray(wave)[:,None]);df=hz[1]-hz[0]
    return np.array([power[(hz>=lo)&(hz<hi)].sum()*df for lo,hi in EDGES])


def assess(profile,targets,duration,seeds):
    total=float(targets.sum());rows=[]
    for seed in seeds:
        powers=band_powers(synth(profile,seed=seed,seconds=duration));bands=[]
        for (lo,hi),target,actual in zip(EDGES,targets,powers):
            significant=bool(target>=total*1e-4)
            error=float(10*np.log10(max(actual,1e-30)/max(target,1e-30)))
            passed=abs(error)<=3 if significant else actual<=max(target*2,total*2e-4)
            bands.append(dict(hz=[lo,hi],target_power=float(target),generated_power=float(actual),
                error_db=error,significant_target=significant,passed=bool(passed)))
        rows.append(dict(seed=seed,bands=bands,qualified=all(b['passed'] for b in bands)))
    return rows


def finite_basis(profile,duration,seeds=TRAIN_SEEDS):
    """Per-seed Gram matrices retain finite modal/noise and noise/noise cross power."""
    members=[(kind,i) for kind in ('modes','bands') for i,row in enumerate(profile[kind]) if row['amplitude']>0]
    if not members:raise ValueError('No nonzero event response basis')
    matrices=[]
    for seed in seeds:
        waves=[]
        for kind,index in members:
            basis=deepcopy(profile);basis['level']=1.
            for group in ('modes','bands'):
                for i,row in enumerate(basis[group]):
                    if group!=kind or i!=index:row['amplitude']=0.
            waves.append(synth(basis,seed=seed,seconds=duration))
        waves=np.column_stack(waves);count=len(members);gram=np.zeros((len(EDGES),count,count))
        for i in range(count):
            for j in range(i,count):
                f,cross=signal.csd(waves[:,i],waves[:,j],48000,nperseg=min(2048,len(waves)),detrend=False)
                for k,(lo,hi) in enumerate(EDGES):
                    use=(f>=lo)&(f<hi);gram[k,i,j]=gram[k,j,i]=float(cross[use].real.sum()*(f[1]-f[0]))
        matrices.append(gram)
    return members,np.array(matrices)


def objective(gram,targets):
    floor=float(targets.sum())*1e-6
    def residual(gain):
        power=np.einsum('i,sbij,j->sb',gain,gram,gain)
        return (np.log(np.maximum(power,0)+floor)-np.log(targets+floor)).ravel()
    def jacobian(gain):
        power=np.einsum('i,sbij,j->sb',gain,gram,gain)
        return (2*np.einsum('sbij,j->sbi',gram,gain)/(np.maximum(power,0)+floor)[:,:,None]).reshape(-1,len(gain))
    return residual,jacobian


def calibrate(profile,targets,duration):
    total=float(targets.sum())
    if total<=1e-20:raise ValueError('No positive spectral excess for response fitting')
    members,gram=finite_basis(profile,duration);scale=np.maximum(targets,total*1e-4)
    diagonal=np.diagonal(gram.mean(axis=0),axis1=1,axis2=2)
    initial,_=optimize.nnls(diagonal/scale[:,None],targets/scale,maxiter=400)
    initial=np.clip(np.sqrt(initial),1e-6,63.)
    residual,jacobian=objective(gram,targets)
    result=optimize.least_squares(residual,initial,jac=jacobian,bounds=(0,64),max_nfev=240,
        ftol=1e-10,xtol=1e-10,gtol=1e-10)
    fitted=deepcopy(profile);fitted['level']=1.
    for gain,(kind,index) in zip(result.x,members):fitted[kind][index]['amplitude']*=float(gain)
    level=max([1.]+[m['amplitude']/4 for m in fitted['modes']]+[b['amplitude']/8 for b in fitted['bands']])
    fitted['level']=min(8.,level)
    for kind in ('modes','bands'):
        for row in fitted[kind]:row['amplitude']/=level
    validate(fitted);training=assess(fitted,targets,duration,TRAIN_SEEDS)
    qualified=bool(level<=8 and all(row['qualified'] for row in training))
    powers=np.array([[b['generated_power'] for b in row['bands']] for row in training])
    errors=np.log(powers+total*1e-6)-np.log(targets+total*1e-6)
    return fitted,dict(qualified=qualified,training=training,groups=len(members),
        amplitude_contract_fits=bool(level<=8),evaluations=result.nfev,optimizer_terminated=bool(result.success),
        score_max_log_error=float(np.max(abs(errors))),score_log_rmse=float(np.sqrt(np.mean(errors**2))))


def search(profile,arrays,duration):
    targets=target_powers(arrays);candidates=[];attempts=[]
    for cutoff in CUTOFFS:
        candidate=deepcopy(profile)
        if cutoff:candidate['noise_lowpass_hz']=cutoff
        else:candidate.pop('noise_lowpass_hz',None)
        fitted,report=calibrate(candidate,targets,duration)
        attempts.append(dict(noise_lowpass_hz=cutoff,**report))
        candidates.append((not report['qualified'],report['score_max_log_error'],report['score_log_rmse'],fitted,report))
    _,_,_,fitted,report=min(candidates,key=lambda row:row[:3])
    # Held-out data never choose a cutoff, alter the solve or retry a candidate.
    held=assess(fitted,targets,duration,HELD_OUT_SEEDS)
    report.update(method='source-response-ensemble-v1',training_qualified=report['qualified'],
        qualified=bool(report['qualified'] and all(row['qualified'] for row in held)),held_out=held,
        training_seeds=list(TRAIN_SEEDS),held_out_seeds=list(HELD_OUT_SEEDS),
        noise_lowpass_hz=fitted.get('noise_lowpass_hz',0.),attempts=attempts,
        target_positive_psd_excess_power=float(targets.sum()),
        policy='Four fixed training excitations, same six spectral gates and <=16 amplitudes; six fixed noise cutoffs; max240 evaluations each. Cutoff selected only by training qualification/worst log error/RMSE, then four untouched held-out excitations.',
        limitations='Finite-seed validation does not bound arbitrary seeds or recreate a full event. No new frequencies/phases/envelopes/room, no source separation or physical identity; source recording and timbre still require review.')
    return fitted,report
