"""Analyze one cropped event and export editable parameters + pure-synthesis preview."""
import argparse
import json
from pathlib import Path
import shutil
import sys


def author(job_path,output,dependency_path=None):
    if dependency_path:sys.path.insert(0,str(dependency_path))
    import numpy as np
    import soundfile as sf
    from event_authoring.audio import read,sha
    from event_authoring.measure import observe
    from event_authoring.fit import fit
    from event_authoring.model import synth,KINDS
    from event_authoring.band_scope import normalize,admission
    job_path=Path(job_path);job=json.loads(job_path.read_text(encoding='utf-8-sig'))
    if job['schema'] not in ('vsl.event-authoring-job/1','vsl.event-authoring-job/2','vsl.event-authoring-job/3','vsl.event-authoring-job/4','vsl.event-authoring-job/5','vsl.event-authoring-job/6','vsl.event-authoring-job/7','vsl.event-authoring-job/8','vsl.event-authoring-job/9','vsl.event-authoring-job/10','vsl.event-authoring-job/11') or job['kind'] not in KINDS:raise ValueError('Invalid event job')
    scope=normalize(job.get('analysis_scope'))
    if job['schema']=='vsl.event-authoring-job/1' and scope['mode']!='full':
        raise ValueError('Frequency scope requires event-authoring-job/2')
    response_fit=job.get('response_fit','legacy')
    ensemble=response_fit=='source-response-ensemble-v1'
    if ensemble and (job['schema']!='vsl.event-authoring-job/11' or scope['mode']!='full'):
        raise ValueError('Ensemble response fit requires a full-band event-authoring-job/11')
    if job['schema']=='vsl.event-authoring-job/11' and not ensemble:
        raise ValueError('Job/11 requires source-response-ensemble-v1')
    if not ensemble and (response_fit not in ('legacy','source-response-v1') or (response_fit!='legacy' and
        (job['schema'] not in ('vsl.event-authoring-job/3','vsl.event-authoring-job/4','vsl.event-authoring-job/5','vsl.event-authoring-job/6','vsl.event-authoring-job/7','vsl.event-authoring-job/8','vsl.event-authoring-job/9','vsl.event-authoring-job/10') or scope['mode']!='full'))):
        raise ValueError('Source response fit requires a full-band event-authoring-job/3')
    envelope_fit=job.get('envelope_fit','legacy')
    if envelope_fit not in ('legacy','band-attack-v1','band-contour-v1','band-contour-v2','band-contour-v3','band-contour-v4','band-contour-v5') or (envelope_fit!='legacy' and
        (job['schema'] not in ('vsl.event-authoring-job/4','vsl.event-authoring-job/5','vsl.event-authoring-job/6','vsl.event-authoring-job/7','vsl.event-authoring-job/8','vsl.event-authoring-job/9') or response_fit!='source-response-v1' or scope['mode']!='full')):
        raise ValueError('Band envelopes require a full-band job/4 with source-response-v1')
    if envelope_fit=='band-contour-v1' and job['schema']!='vsl.event-authoring-job/5':raise ValueError('Contours require job/5')
    if envelope_fit=='band-contour-v2' and job['schema']!='vsl.event-authoring-job/6':raise ValueError('Reliable contours require job/6')
    if envelope_fit=='band-contour-v3' and job['schema']!='vsl.event-authoring-job/7':raise ValueError('Adaptive contours require job/7')
    if envelope_fit=='band-contour-v4' and job['schema']!='vsl.event-authoring-job/8':raise ValueError('Four-band contours require job/8')
    if envelope_fit=='band-contour-v5' and job['schema']!='vsl.event-authoring-job/9':raise ValueError('Simultaneous contours require job/9')
    source=Path(job['source'])
    if not source.is_absolute():source=(job_path.parent/source).resolve()
    x,sr,provenance=read(source,*job['seconds']);background,_,background_source=read(source,*job['background_seconds'])
    duration=len(x)/sr
    minimum=.008 if job['schema'] in ('vsl.event-authoring-job/10','vsl.event-authoring-job/11') else .06
    if duration<minimum or duration>5:raise ValueError(f'One event crop must be {minimum}–5 seconds')
    if job['schema']=='vsl.event-authoring-job/10' and (duration>=.06 or job.get('gated',False) or envelope_fit!='legacy'):
        raise ValueError('Short job/10 requires an8–60ms non-gated event without long-window envelope fitting')
    if ensemble and duration<.06 and job.get('gated',False):
        raise ValueError('Short ensemble events cannot be gated')
    observation,arrays=observe(x,background,scope)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    shutil.copy2(job_path,output/'input.job.json')
    exact=output/'exact_sources';exact.mkdir()
    for path in [Path(__file__),*sorted((Path(__file__).parent/'event_authoring').glob('*.py'))]:shutil.copy2(path,exact/path.name)
    if admission(observation)<3:
        result=dict(status='analysis_only',reason='Declared-scope event/background contrast <3 dB; no profile compiled',
            observation=observation,provenance=provenance,background=background_source,source_job=job)
        (output/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        sf.write(output/'reference.wav',x,sr,subtype='FLOAT')
        return dict(output=str(output),kind=job['kind'],status='analysis_only',event_to_background_db=observation['event_to_background_db'],
            analysis_scope=scope,admission_contrast_db=admission(observation))
    profile,policy=fit(observation,arrays,duration,job.get('gated',False))
    if envelope_fit in ('band-attack-v1','band-contour-v1','band-contour-v2','band-contour-v3','band-contour-v4','band-contour-v5'):
        from event_authoring.temporal_fit import fit as fit_envelopes
        profile,envelopes=fit_envelopes(profile,x,background)
        policy=dict(policy,temporal_fit=envelopes)
    if response_fit in ('source-response-v1','source-response-ensemble-v1'):
        if ensemble:from event_authoring.response_ensemble import search
        else:from event_authoring.response_fit import search
        profile,response=search(profile,arrays,duration)
        if envelope_fit=='band-contour-v1' and response['qualified']:
            from event_authoring.contour_fit import fit as fit_contours
            from event_authoring.response_fit import calibrate
            policy=dict(policy,initial_source_response_fit=response)
            profile,contours=fit_contours(profile,x,background)
            profile,response=calibrate(profile,arrays,duration)
            policy=dict(policy,contour_fit=contours)
        joint_refused=False
        if envelope_fit in ('band-contour-v2','band-contour-v3','band-contour-v4','band-contour-v5') and response['qualified']:
            if envelope_fit=='band-contour-v5':from event_authoring.contour_joint_response import fit as fit_joint
            elif envelope_fit=='band-contour-v4':from event_authoring.contour_all_bands import fit as fit_joint
            elif envelope_fit=='band-contour-v3':from event_authoring.contour_adaptive import fit as fit_joint
            else:from event_authoring.contour_joint import fit as fit_joint
            policy=dict(policy,initial_source_response_fit=response)
            profile,contours,calibrated=fit_joint(profile,x,background,arrays)
            if calibrated is not None:response=calibrated
            joint_refused=not contours['qualified']
            policy=dict(policy,contour_fit=contours)
        policy=dict(policy,source_response_fit=response)
        if not response['qualified'] or joint_refused:
            refusal_kind='contour_fit' if joint_refused else 'response_fit'
            result=dict(status='analysis_only',refusal_kind=refusal_kind,
                reason='Reliable contour/response requirements not met; no profile compiled' if joint_refused else
                    'Source response fit exceeds declared limits; no profile compiled',observation=observation,
                fit=policy,provenance=provenance,background=background_source,source_job=job)
            (output/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
            (output/'refused-fit.json').write_text(json.dumps(profile,indent=2,allow_nan=False),encoding='utf-8')
            sf.write(output/'reference.wav',x,sr,subtype='FLOAT')
            return dict(output=str(output),kind=job['kind'],status='analysis_only',refusal_kind=refusal_kind,
                event_to_background_db=observation['event_to_background_db'],analysis_scope=scope,
                admission_contrast_db=admission(observation),**(dict(response_summary=dict(
                    method=response_fit,training_qualified=response['training_qualified'],
                    held_out_qualified=all(r['qualified'] for r in response['held_out']),qualified=False)) if ensemble else {}))
    if policy.get('scope_band_fit_qualified') is False:
        result=dict(status='analysis_only',refusal_kind='band_fit',
            reason='Declared-band fit error exceeds limits; no profile compiled',observation=observation,
            fit=policy,provenance=provenance,background=background_source,source_job=job)
        (output/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        (output/'refused-fit.json').write_text(json.dumps(profile,indent=2,allow_nan=False),encoding='utf-8')
        sf.write(output/'reference.wav',x,sr,subtype='FLOAT')
        return dict(output=str(output),kind=job['kind'],status='analysis_only',refusal_kind='band_fit',
            event_to_background_db=observation['event_to_background_db'],analysis_scope=scope,
            admission_contrast_db=admission(observation))
    preview=synth(profile,seconds=duration)
    sf.write(output/'reference.wav',x,sr,subtype='FLOAT');sf.write(output/'synthesis.wav',preview,sr,subtype='FLOAT')
    document=dict(schema='vsl.event-profile/4' if profile.get('contours') else
        'vsl.event-profile/3' if any(m.get('attack_seconds',0) for m in profile['modes']) else
        'vsl.event-profile/2' if profile.get('noise_lowpass_hz',0) else 'vsl.event-profile/1',kind=job['kind'],name=job['name'],parameters=profile,
        provenance=provenance,background=background_source,observation=observation,fit=policy,
        physical_identity_confirmed=bool(job.get('physical_identity_confirmed',False)),
        status='material-informed candidate; listening not yet accepted',context=job.get('context',''),
        source_job=job,generated_peak=float(np.max(np.abs(preview))),generated_rms=float(np.sqrt(np.mean(preview**2))),
        runtime='damped sine modes and procedural-noise SOS bands; optional noise-only fourth-order lowpass; no recording playback or room effect')
    (output/'profile.json').write_text(json.dumps(document,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    manifest={p.name:sha(p) for p in output.iterdir() if p.is_file()}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return dict(output=str(output),kind=job['kind'],event_to_background_db=observation['event_to_background_db'],
                analysis_scope=scope,admission_contrast_db=admission(observation),
                modes=len(profile['modes']),bands=len(profile['bands']),peak=document['generated_peak'],rms=document['generated_rms'],
                **(dict(response_summary=dict(method=response_fit,training_qualified=response['training_qualified'],
                    held_out_qualified=all(r['qualified'] for r in response['held_out']),qualified=response['qualified'])) if ensemble else {}))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('job',type=Path)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--dependencies',type=Path)
    args=parser.parse_args();result=author(args.job,args.output,args.dependencies)
    print(json.dumps(result,ensure_ascii=False))
    if result.get('status')=='analysis_only':raise SystemExit(3)


if __name__=='__main__':main()
