"""Encode frozen idle parameters once; no fitting, tuning or timeline export."""
import argparse,hashlib,json,shutil
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[1]
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},inputs={})
try:
    source=a.workspace/'references/analysis/idle_modal_v1/trial4/profile.json'
    audit=a.workspace/'references/analysis/idle_modal_v1/audit2/report.json'
    summary=load(repo/'research/idle_material_modal_v1_summary.json')
    frozen=a.workspace/summary['freeze'];assert sha(frozen/'manifest.json')==summary['manifest_sha256']
    assert sha(source)==sha(frozen/'evidence/idle_modal_v1/trial4/profile.json')
    assert load(audit)['profile_has_no_observation_timeline']
    data=load(source);m=data['modal'];assert 'evidence' not in m and not data['recorded_trajectory']
    target=repo/'experiments/modal_idle_v1'
    modal_path=target/'F2_fixed_idle.msource';detail_path=target/'F2_fixed_idle.rdetail'
    assert not modal_path.exists() and not detail_path.exists()
    lines=[f"VSL_MODAL_SOURCE 1 48000 {len(m['frequencies_hz'])}"]
    for hz,amp,phase in zip(m['frequencies_hz'],m['amplitude_LR'],m['initial_phase_LR']):
        lines.append(' '.join(format(v,'.17g') for v in [hz,*amp,*phase]))
    modal_path.write_text('\n'.join(lines)+'\n',encoding='ascii')
    # This scalar is required by the existing Rdt format; zero-order envelopes
    # make it unused by sampling. It is NOT an engine/root/RPM observation.
    base=m['frequencies_hz'][0]
    lines=[f"VSL_RESONANT_DETAIL 1 48000 {len(data['resonators'])} 96000 {base:.17g}"]
    for model in data['resonators']:
        assert not any(model['envelope']['coefficients'])
        lines.append(f"{len(model['a'])-1} {len(model['sos'])} 0")
        lines.append(' '.join(format(v,'.17g') for v in [*model['band_hz'],model['sigma'],model['gain'],model['right_over_left']]))
        lines.append(' '.join(format(v,'.17g') for v in model['a']))
        lines.extend(' '.join(format(v,'.17g') for v in row) for row in model['sos'])
    detail_path.write_text('\n'.join(lines)+'\n',encoding='ascii')
    # Exact Python text round-trip of every scalar; C loading is tested next.
    rows=[[float(v) for v in row.split()] for row in modal_path.read_text().splitlines()[1:]]
    assert rows==[[hz,*amp,*phase] for hz,amp,phase in zip(m['frequencies_hz'],m['amplitude_LR'],m['initial_phase_LR'])]
    tokens=iter(detail_path.read_text().split());assert [next(tokens) for _ in range(6)]==['VSL_RESONANT_DETAIL','1','48000','6','96000',format(base,'.17g')]
    for model in data['resonators']:
        assert [int(next(tokens)) for _ in range(3)]==[len(model['a'])-1,len(model['sos']),0]
        expected=[*model['band_hz'],model['sigma'],model['gain'],model['right_over_left'],*model['a'],*[v for row in model['sos'] for v in row]]
        assert [float(next(tokens)) for _ in expected]==expected
    assert next(tokens,None) is None
    files=[Path(__file__),repo/'research/idle_modal_c_v1_plan.json']
    for folder in ['modules/modal_source','experiments/modal_idle_v1']:
        files.extend(path for path in (repo/folder).iterdir() if path.is_file())
    for path in files:
        dest=a.out/'exact_sources'/path.relative_to(repo);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
        r['sources'][path.relative_to(repo).as_posix()]=sha(path)
    r.update(result='frozen_parameters_encoded_exactly_no_refit',parent_profile_sha256=sha(source),
        parent_manifest_sha256=summary['manifest_sha256'],modal_profile_sha256=sha(modal_path),detail_profile_sha256=sha(detail_path),
        Rdt_base_hz_role='Unused reference metadata; all periodic envelopes zero-order; no shared source clock',
        no_PCM_or_timeline=True,listening_accepted=False,driver_integrated=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(json.dumps(dict(result=r['result'],modal=r.get('modal_profile_sha256'),detail=r.get('detail_profile_sha256'))),flush=True)
