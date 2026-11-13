"""Independently verify reviewed source permissions, exact clips and raw F2 spectra."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha,read


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F-state-observation-audit/1',result='running',sources={},real_audio_read=True,
    phase_estimator_run=False,model_exported=False,runtime_changed=False)
try:
    base=args.workspace/'references/analysis'
    audition=load(base/'F_state_audition_v1/review1/report.json')
    registered=load(base/'F_state_catalog_v1/register1/report.json')
    measured=load(base/'F2_idle_observation_v1/measure1/report.json')
    paths={Path(__file__)}
    for location,value in ((base/'F_state_audition_v1/review1',audition),
        (base/'F_state_catalog_v1/register1',registered),(base/'F2_idle_observation_v1/measure1',measured)):
        for relative,digest in value['sources'].items():
            assert sha(repo/relative)==sha(location/'exact_sources'/relative)==digest
            paths.add(repo/relative)
    for path in paths:
        relative=path.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
        report['sources'][relative.as_posix()]=sha(path)
    catalogue=load(repo/'references/segments_v1.json')
    before=load(base/'F_state_catalog_v1/register1/catalogue_before.json')
    assert sha(repo/'references/segments_v1.json')==registered['catalogue_sha256']==sha(args.workspace/'references/segments_v1.json')
    assert all(catalogue['sources'][key]==value for key,value in before['sources'].items())
    assert all(catalogue['segments'][key]==value for key,value in before['segments'].items())
    assert catalogue['segments']['F3_stopped']['allowed_uses']==['source_usability_review']
    try:
        read(args.workspace,'F3_stopped','recording_power')
    except AssertionError:
        permission_rejection=True
    else:
        raise AssertionError('Speech-masked F3 segment unexpectedly allowed quantitative analysis')
    for row in audition['clips']:
        master=args.workspace/row['source_master']
        assert sha(master)==row['source_master_sha256']
        assert sha(args.workspace/row['original_encoded'])==row['original_encoded_sha256']
        with sf.SoundFile(master) as stream:
            first,stop=[round(t*48000) for t in row['actual_seconds']]
            stream.seek(first);expected=stream.read(stop-first,dtype='float64',always_2d=True)
        file=base/'F_state_audition_v1/review1'/row['file']
        actual,rate=sf.read(file,dtype='float64',always_2d=True)
        assert rate==48000 and np.array_equal(expected,actual) and sha(file)==row['sha256']
    audio,provenance=read(args.workspace,'F2_tailpipe','recording_power')
    assert provenance==measured['provenance']
    saved=np.load(base/'F2_idle_observation_v1/measure1/observations.npz')
    assert np.array_equal(audio,saved['whole_audio'])
    assert sha(base/'F2_idle_observation_v1/measure1/observations.npz')==measured['arrays_sha256']
    rate=48000;window=.5-.5*np.cos(2*np.pi*np.arange(rate)/rate)
    hz=np.fft.rfftfreq(rate,1/rate)
    assert np.array_equal(hz,saved['hz'])
    factors=np.full(len(hz),2.);factors[[0,-1]]=1.
    def spectrum(part):
        fft=np.array([np.fft.rfft(part[start:start+rate]*window[:,None],axis=0)
            for start in range(0,len(part)-rate+1,rate//2)])
        return (abs(fft)**2*factors[None,:,None]/(rate*np.sum(window**2))).mean(axis=0).T
    independent=np.array([spectrum(audio[j*2*rate:(j+1)*2*rate]) for j in range(3)])
    psd_error=float(abs(independent-saved['block_psd']).max())
    whole_error=float(abs(spectrum(audio)-saved['whole_mean_psd']).max())
    bands=measured['whole_recording']['bands_Hz']
    power=np.stack([independent[:,:,(hz>=lo)&(hz<hi)].sum(axis=2) for lo,hi in bands],axis=2)
    power_error=float(abs(power-saved['block_mean_band_power']).max())
    span=10*np.log10(power.max(axis=0)/power.min(axis=0))
    span_error=float(abs(span-np.asarray(measured['three_block_recording_band_span_db_LR'])).max())
    assert max(psd_error,whole_error,power_error)<=1e-12 and span_error<=1e-10
    # Display-only native1Hz bin peaks; never select a fundamental or infer RPM.
    strongest=[]
    for j in range(3):
        psd=independent[j,0]
        candidates=np.flatnonzero((psd[1:-1]>psd[:-2])&(psd[1:-1]>=psd[2:]))+1
        candidates=candidates[(hz[candidates]>=20)&(hz[candidates]<250)]
        selected=sorted(candidates,key=lambda k:psd[k],reverse=True)[:5]
        strongest.append(dict(source_seconds=[6+2*j,8+2*j],L_native1Hz_peak_bins_Hz=[float(hz[k]) for k in selected]))
    report.update(result='reviewed_F_source_permissions_exact_clips_and_F2_Fourier_observations_independently_verified',
        audition_report_sha256=sha(base/'F_state_audition_v1/review1/report.json'),
        catalogue_report_sha256=sha(base/'F_state_catalog_v1/register1/report.json'),
        F2_report_sha256=sha(base/'F2_idle_observation_v1/measure1/report.json'),
        all7_source_clips_exact=True,prior_catalogue_entries_unchanged=True,
        speech_masked_F3_quantitative_use_rejected=permission_rejection,
        independent_PSD_error=psd_error,independent_whole_PSD_error=whole_error,
        independent_band_power_error=power_error,independent_span_db_error=span_error,
        display_only_low_band_peaks=strongest,phase_or_RPM_inferred=False,
        limits=measured['limits'])
    print(json.dumps(dict(result=report['result'],PSD_error=psd_error,band_error=power_error,peaks=strongest)),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc));raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
