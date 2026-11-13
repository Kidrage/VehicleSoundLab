"""Extract approved idle material statistics and the actual demo coverage gap."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
args = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools'/x) for x in ('ipm_deps', 'qp_deps', 'python_deps')]
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha, read
from idle_material_v1.features import observe, controls


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path, value): path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


args.out.mkdir(parents=True, exist_ok=False)
r = dict(schema='vsl.idle-material-analysis/1', result='running', sources={}, observations=[],
    new_DNA=False, runtime_changed=False, new_audio=False, common_phase_fit=False)
try:
    plan_path = repo/'research/idle_material_v1_plan.json'; plan = load(plan_path)
    bands = [[30,120], [120,400], [400,1200], [1200,2200], [2200,4000], [4000,8000], [8000,14000]]
    sources = [Path(__file__), plan_path, repo/'tools/idle_material_v1/features.py', repo/'tools/drive_evidence_v1/sources.py',
        repo/'modules/dna_atlas/voice.c', repo/'modules/drive_recipe/voice.c', repo/'modules/drive_recipe/shape.c',
        repo/'modules/drive_resonance/voice.c', repo/'experiments/full_recipe_drive_v1/models.c',
        repo/'voices/dna_bank_v1/V10 Exterior.model', repo/'research/F_state_audition_v1_review.json']
    for path in sources:
        rel = path.relative_to(repo); dest = args.out/'exact_sources'/rel
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
        r['sources'][rel.as_posix()] = sha(path)
    r['controls'] = controls(bands)
    catalog = load(args.workspace/'references/segments_v1.json')
    assert sha(repo/'references/segments_v1.json') == sha(args.workspace/'references/segments_v1.json')
    r['catalogue_sha256'] = sha(args.workspace/'references/segments_v1.json')
    r['inventory'] = [dict(id=key, raw=value['raw'], raw_sha256=value['raw_sha256'],
        master=value['master'], master_sha256=value['master_sha256']) for key,value in catalog['sources'].items()]
    for item in r['inventory']:
        assert sha(args.workspace/item['raw']) == item['raw_sha256']
        assert sha(args.workspace/item['master']) == item['master_sha256']
    arrays = {}
    for item in plan['sources']:
        audio, provenance = read(args.workspace, item['id'], item['use'])
        first, stop = [round((t-provenance['seconds'][0])*48000) for t in item['seconds']]
        audio = audio[first:stop]; assert len(audio) == round((item['seconds'][1]-item['seconds'][0])*48000)
        measured = observe(audio, bands)
        frequency, cells = measured.pop('frequency'), measured.pop('average_cell_power')
        name = item['id']
        arrays[name+'_audio'] = audio
        arrays[name+'_cells'] = cells
        arrays['frequency'] = frequency
        r['observations'].append(dict(id=name, source_seconds=item['seconds'], purpose=item['purpose'],
            provenance=provenance, **measured))
    folder = args.workspace/'references/analysis/full_recipe_drive_v1/verify1/full_pedals'
    trace = np.genfromtxt(folder/'pedal_trace.csv', delimiter=',', names=True)
    state = load(folder/'state_inspection.json')
    mask = (trace['lifecycle'] == 4)&(trace['operating'] == 0)
    first = int(trace['frame'][np.flatnonzero(mask)[0]])
    stop = first+24000
    selected = trace[(trace['frame'] >= first)&(trace['frame'] < stop)]
    assert np.all((selected['lifecycle'] == 4)&(selected['operating'] == 0))
    assert selected['frame'][-1] >= stop-240
    stems = {}; r['runtime_inputs'] = {}
    for name in ('recorded', 'dna_stem', 'detail_stem', 'coherent_low_stem'):
        file = folder/(name+'.wav'); audio, rate = sf.read(file, always_2d=True)
        assert rate == 48000 and np.isfinite(audio).all()
        stems[name] = audio[first:stop]
        r['runtime_inputs'][file.relative_to(args.workspace).as_posix()] = sha(file)
    for name in ('pedal_trace.csv', 'state_inspection.json'):
        file = folder/name; r['runtime_inputs'][file.relative_to(args.workspace).as_posix()] = sha(file)
    assert np.count_nonzero(stems['detail_stem']) == np.count_nonzero(stems['coherent_low_stem']) == 0
    assert np.max(selected['resonant_support']) == np.max(selected['coherent_low_support']) == 0
    header = (repo/'voices/dna_bank_v1/V10 Exterior.model').read_text(encoding='ascii').splitlines()[0].split()
    assert header[0] in ('VSL_SUSTAIN_OSC', 'VSL_SOUND_DNA')
    harmonics = int(header[5])
    base = int(header[2])/int(header[3]) if header[0] == 'VSL_SUSTAIN_OSC' else float(header[7])
    assert harmonics == 300 and base == 46.875
    measured = observe(stems['recorded'], bands)
    arrays['runtime_cells'] = measured.pop('average_cell_power'); measured.pop('frequency')
    arrays['runtime_audio'] = stems['recorded']
    r['observations'].append(dict(id='runtime_full_recipe_idle', **measured))
    r['runtime'] = dict(frame_interval=[first, stop], seconds=[first/48000, stop/48000],
        RPM_range=[float(selected['rpm'].min()), float(selected['rpm'].max())],
        acoustic_root_range=[float(selected['root_hz'].min()), float(selected['root_hz'].max())],
        harmonics=harmonics, highest_main_carrier_range=[float(harmonics*selected['root_hz'].min()), float(harmonics*selected['root_hz'].max())],
        detail_support=0., coherent_low_support=0., detail_samples_exact_zero=True, low_samples_exact_zero=True,
        recorded_scope='Existing actual C device output; this short stable tile is not a full idle quality acceptance or long-run check',
        source_RPM_mapping='engineering1/120, not measured ECU/source RPM')
    np.savez_compressed(args.out/'observations.npz', **arrays)
    r.update(result='four_raw_contexts_and_actual_idle_coverage_extracted', bands_hz=bands,
        observations_sha256=sha(args.out/'observations.npz'), full_goal_complete=False,
        excluded_contexts=dict(F1='multi-car/moving-mic, scene review only', B='cabin candidates previously failed stationary full-timbre support',
            D='dyno gear context, not confirmed idle', F3='stationary speech masks engine, excluded'),
        next='Use the F2 idle-specific spectrum and temporal band variation to define a separate same-perspective state recipe; do not brighten or transpose the retained moving35 profile as an idle solution. Common-phase qualification remains required before its real DNA export.',
        limits=['Recording band power is not physical source separation or a noise/OSC allocation.',
            'Highest main carrier is not a brick-wall cutoff; stochastic modulation sidebands and finite-window leakage remain.',
            'F2 LP-610 and A/E Performante contexts are kept separate; mic motion, wind, thermal state and exact RPM remain uncalibrated.',
            'Phase-free evidence only; no common-phase estimate, new profile, C change or audible improvement claim.'])
except Exception as exc:
    r.update(result='failed', error=repr(exc)); raise
finally:
    save(args.out/'report.json', r)
print(json.dumps(dict(result=r['result'], runtime=r['runtime'], above2200_fractions=[dict(id=o['id'], fraction=float(np.array(o['fraction_of_mean_band_power'])[4:,0].sum())) for o in r['observations']]), ensure_ascii=False), flush=True)
