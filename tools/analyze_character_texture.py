"""Test what native character layers actually add, without changing voicing."""
import json
import csv
from pathlib import Path
from runtime_review import ROOT,sha
from reference_segments import read_segment
from cycle_prediction import phase_grid,predict,band_prediction,CycleSettings
from texture_metrics import measure,TextureSettings
import numpy as np
import soundfile as sf
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=ROOT/'references/analysis/character_texture_v1'
RATE=48000
VARIANTS=['base','pressure','structure','combined']

def controls():
    t=np.arange(4*RATE)/RATE;frequency=60+20*np.sin(2*np.pi*.7*t)
    phase=2*np.pi*(60*t+20/(2*np.pi*.7)*(1-np.cos(2*np.pi*.7*t)))
    rng=np.random.default_rng(48271);x=np.zeros((len(t),2))
    for k in [1,3,7,17,43,79]:
        for c in range(2):x[:,c]+=.04/np.sqrt(k)*np.cos(k*phase+.2*k+.4*c)
    track_times=np.arange(.1,3.9,.002);f=60+20*np.sin(2*np.pi*.7*track_times)
    grid,meta,inverse=phase_grid(x,RATE,track_times,f)
    # Analytic waveform at queried source times is an independent interpolator check.
    tt=inverse.ravel();pp=2*np.pi*(60*tt+20/(2*np.pi*.7)*(1-np.cos(2*np.pi*.7*tt)))
    exact=np.column_stack([sum(.04/np.sqrt(k)*np.cos(k*pp+.2*k+.4*c) for k in [1,3,7,17,43,79]) for c in range(2)]).reshape(grid.shape)
    interpolation_db=float(10*np.log10(np.mean((grid-exact)**2)/np.mean(exact**2)))
    assert interpolation_db< -55,interpolation_db
    known=predict(grid);assert max(known['error_to_signal_db_lr'])< -38,known
    swapped,_,_=phase_grid(x[:,::-1],RATE,track_times,f);assert np.array_equal(swapped,grid[:,:,::-1])
    scaled=predict(grid*.31);assert np.max(abs(np.array(scaled['error_to_signal_db_lr'])-known['error_to_signal_db_lr']))<1e-8
    # Leakage control: a future-only impulse must never influence a past template.
    example=np.zeros((20,128,2));example[8:12]=1
    test=predict(example);assert test['folds'][0]['train_cycle_indices']==[0,8]
    assert test['folds'][0]['test_cycle_indices']==[8,12]
    assert np.max(abs(np.array(test['error_to_signal_db_lr'])-10*np.log10(1.5)))<1e-12
    # Independent random complete cycles have E(error power)/E(signal power)=1+1/Ntrain.
    random_grid=rng.normal(0,.1,size=(500,256,2));random_result=predict(random_grid)
    expected_db=float(10*np.log10(1+1/8))
    assert np.max(abs(np.array(random_result['error_to_signal_db_lr'])-expected_db))<.05
    # Deliberately wrong phase path is a stress test, not a confidence interval.
    stressed,_,_=phase_grid(x,RATE,track_times,f+.5*np.sin(2*np.pi*5*track_times))
    stress=predict(stressed)
    return dict(analytic_chirp=known,interpolation_error_db=interpolation_db,
        exact_channel_swap=True,gain_invariance=True,future_template_leakage=False,
        random_cycles=random_result,random_expected_error_db=expected_db,phase_path_stress=stress,
        settings=CycleSettings().__dict__)

def read_audio(path):
    x,rate=sf.read(path,always_2d=True);assert rate==RATE and np.isfinite(x).all() and sf.info(path).subtype=='FLOAT'
    return x

def compact(rows,band=(3000,8000),divisor=5):
    return next(r for r in rows if r['band_hz']==list(band) and r['divisor']==divisor)

def main():
    if (OUT/'results.json').exists():raise SystemExit('Preserve completed character_texture_v1.')
    OUT.mkdir(parents=True,exist_ok=True);control=controls();runtime={};inputs={}
    native=json.loads((ROOT/'renders/v0.16.0/verification.json').read_text())
    # Mid has all four independently rendered native variants. Low/high pairs
    # are used for RPM dependence rather than inventing new native voicing.
    for case,rpm in [('low',1200),('mid',4000),('high',8000)]:
        runtime[case]={};path=ROOT/f'renders/v0.16.0/{case}_base.wav';base=read_audio(path)
        for tag in (VARIANTS if case=='mid' else ['base','combined']):
            path=ROOT/f'renders/v0.16.0/{case}_{tag}.wav'
            assert sha(path)==native['files'][path.name];inputs[str(path.relative_to(ROOT))]=sha(path)
            x=read_audio(path);steady=x[120000:230400];b=base[120000:230400]
            spectrum,_=measure(steady,RATE,TextureSettings(window=4096,hop=256))
            times=np.arange(2.5,4.8,.005);freq=np.full(len(times),rpm*10/240.)
            prediction=band_prediction(x,RATE,times,freq)
            delta=x-base
            powers={}
            for lo,hi in [(300,1200),(1200,3000),(3000,8000)]:
                sos=signal.butter(4,[lo,hi],btype='bandpass',fs=RATE,output='sos')
                a=signal.sosfilt(sos,base,axis=0)[120000:230400]
                d=signal.sosfilt(sos,delta,axis=0)[120000:230400]
                ratio=(d*d).sum(axis=0)/np.maximum((a*a).sum(axis=0),1e-30)
                powers[f'{lo}_{hi}']=(10*np.log10(np.maximum(ratio,1e-30))).tolist()
            runtime[case][tag]=dict(known_engineering_rpm=rpm,band_texture=spectrum,
                cycle_prediction=prediction,delta_to_baseline_power_db_lr=powers,
                normalized_cycle_frequency='Supplied bank frequency=RPM*10/240; divisor5 is the known full720-degree model cycle. Not a reference RPM estimate.')
        print('native measurements',case,flush=True)
    reference,rate,provenance=read_segment('A_exterior_blips','exterior_dynamic_observation')
    origin=provenance['source_seconds'][0]
    texture_path=ROOT/'references/analysis/texture_v1/results.json'
    old=json.loads(texture_path.read_text());references={}
    for label,row in old['reference_compensation']['runs'].items():
        path=row['path'];assert path['status']=='connected_peak_path' and path['support_fraction']>.99
        times=np.array([r['seconds'] for r in path['rows']]);hz=np.array([r['hz'] for r in path['rows']])
        prediction=band_prediction(reference,rate,times,hz,origin=origin)
        references[label]=dict(provenance=provenance,anchored_path=path,cycle_prediction=prediction,
            physical_rpm=None,limits='Divisors are alternative repeat lengths of one observed ridge, not identified crank/firing orders. Same mixed exterior recording only; not a matched RPM/load/transfer comparison.')
    result=dict(schema='vsl.character-texture/1',version='analysis only; native V016 unchanged',seed=48271,
        controls=control,runtime=runtime,references=references,
        source_results=dict(path=str(texture_path.relative_to(ROOT)),sha256=sha(texture_path)),inputs=inputs,
        definitions=dict(delta='Power of aligned candidate-minus-baseline waveform, relative to baseline in same raw-time band. Not a source power or perceptual difference.',
            prediction='Past8-cycle mean predicts next4 cycles, per channel, in one supplied phase coordinate; full frequency path known. No held-out amplitude/phase fitting.',
            bandpass='4th-order prototype Butterworth causal bandpass, applied separately to unchanged L/R analysis arrays only.',
            limits='No noise percentage, separated pressure/structure, measured cylinder variability, physical phase/RPM or realism score is inferred. Tracking error, changing transfer, other sources and encoding can all affect predictability.'),
        subjective='No new listening acceptance; no runtime parameter or recipe changes.')
    fig,axes=plt.subplots(1,2,figsize=(12,4.7),constrained_layout=True)
    for case in runtime:
        tags=list(runtime[case]);vals=[compact(runtime[case][tag]['cycle_prediction'])['error_to_signal_db_lr'][0] for tag in tags]
        axes[0].plot(tags,vals,'o-',label=f'{runtime[case][tags[0]]["known_engineering_rpm"]} RPM')
    axes[0].set(title='Known C full cycle / original 3-8 kHz / L',ylabel='Future waveform error / actual power (dB)',xlabel='Same fixed driving inputs; no loudness match')
    for label,row in references.items():
        divs=[];vals=[]
        for d in [1,2,5,10]:
            item=compact(row['cycle_prediction'],divisor=d)
            if item['status']=='measured':divs.append(d);vals.append(item['error_to_signal_db_lr'][0])
        axes[1].plot(divs,vals,'o-',label=label)
    axes[1].set(title='A first descent / original 3-8 kHz / L\nUnidentified observed ridge; different conditions',
        xlabel='Observed-ridge periods per candidate repeat',ylabel='Future waveform error / actual power (dB)',xticks=[1,2,5,10])
    for ax in axes:ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.savefig(OUT/'cycle_prediction.png',dpi=160);plt.close(fig)
    with (OUT/'summary.csv').open('w',newline='') as file:
        writer=csv.writer(file);writer.writerow(['source','variant','band_low_hz','band_high_hz','divisor','status','L_error_db','R_error_db','heldout_cycles'])
        for case,variants in runtime.items():
            for tag,row in variants.items():
                for m in row['cycle_prediction']:writer.writerow([case,tag,*m['band_hz'],m['divisor'],m['status'],*m.get('error_to_signal_db_lr',[None,None]),m.get('held_out_cycle_count')])
        for label,row in references.items():
            for m in row['cycle_prediction']:writer.writerow(['A_first_descent',label,*m['band_hz'],m['divisor'],m['status'],*m.get('error_to_signal_db_lr',[None,None]),m.get('held_out_cycle_count')])
    result['files']={p.name:sha(p) for p in OUT.iterdir() if p.is_file()}
    (OUT/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print('character texture measurements complete',flush=True)

if __name__=='__main__':main()
