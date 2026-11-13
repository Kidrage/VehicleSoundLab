"""Independent exact interval and native-frame audits; no PCM read or model fit."""
import argparse
from fractions import Fraction as Q
import hashlib
import itertools
import json
from pathlib import Path
import re
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace / 'tools/python_deps'))
import numpy as np
from PIL import Image, ImageFilter


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def same(left, right):
    if isinstance(left, dict):
        assert left.keys() == right.keys()
        for key in left:
            same(left[key], right[key])
    elif isinstance(left, list):
        assert len(left) == len(right)
        for a, b in zip(left, right):
            same(a, b)
    elif isinstance(left, float):
        assert abs(left - right) <= 1e-12
    else:
        assert left == right


def exact_relations(anchors, orders, extras, half_width):
    anchors, extras = [[Q(str(x)) for x in values] for values in (anchors, extras)]
    half_width = Q(str(half_width))
    lo = max((a-half_width)/n for a, n in zip(anchors, orders))
    hi = min((a+half_width)/n for a, n in zip(anchors, orders))
    if lo > hi or lo <= 0:
        return dict(anchor_interval_Hz=None, branches=[], compatible=False)
    choices = [range(1, int((a+half_width)/lo)+1) for a in extras]
    branches = []
    # Enumerate the Cartesian product then intersect all constraints at once.
    for ns in itertools.product(*choices):
        left = max([lo] + [(a-half_width)/n for a, n in zip(extras, ns)])
        right = min([hi] + [(a+half_width)/n for a, n in zip(extras, ns)])
        if left <= right:
            branches.append(dict(base_interval_Hz=[float(left), float(right)], extra_orders=list(ns)))
    return dict(anchor_interval_Hz=[float(lo), float(hi)], branches=branches, compatible=bool(branches))


def image_mask(root, row, crop=False):
    path = root / row['file']
    assert sha(path) == row['sha256']
    with Image.open(path) as picture:
        picture = picture.convert('RGB')
        if crop:
            picture = picture.crop((65, 130, 240, 338))
        a = np.asarray(picture, dtype=np.int32)
    # Integer inequality, separate from the detector's floating colour helper.
    return (a[..., 0] > 150) & (a[..., 1] > 80) & (a[..., 2] < 100) & (10*a[..., 0] > 11*a[..., 1])


def widened(mask):
    return np.asarray(Image.fromarray(mask.astype(np.uint8)*255).filter(ImageFilter.MaxFilter(3))) > 0


def scores(mask, templates, wide_templates, shape):
    area = int(mask.sum())
    dice = {}
    coverage = {}
    wide = widened(mask) if shape else None
    for key, target in templates.items():
        other = int(target.sum())
        overlap = int((mask & target).sum())
        dice[key] = 2*overlap/(area+other) if area+other else 0.
        if shape:
            coverage[key] = ((int((mask & wide_templates[key]).sum())/area +
                              int((target & wide).sum())/other)/2) if area and other else 0.
    chosen = coverage if shape else dice
    order = sorted(chosen, key=chosen.get, reverse=True)
    best, runner = order[:2]
    margin = chosen[best]-chosen[runner]
    common = dict(displayed_gear=int(best) if chosen[best] >= .9 and margin >= .1 else None,
                  best_template=int(best), margin=margin)
    if shape:
        return dict(**common, best_shape_score=chosen[best], all_shape_scores=coverage,
                    raw_Dice=dice[best], all_raw_Dice=dice)
    return dict(**common, best_Dice=dice[best], all_Dice=dice)


def scalar_shape(mask, target):
    a = set(zip(*np.nonzero(mask)))
    b = set(zip(*np.nonzero(target)))
    def covered(source, destination):
        return sum(any((y+dy, x+dx) in destination for dy in (-1, 0, 1)
                       for dx in (-1, 0, 1)) for y, x in source)
    return (covered(a, b)/len(a)+covered(b, a)/len(b))/2 if a and b else 0.


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.F-state-evidence-audit/1', result='running', sources={},
              audio_read=False, phase_estimator_run=False, model_exported=False, runtime_changed=False)
try:
    base = args.workspace / 'references/analysis'
    f2root = base / 'F2_period_relation_v1/observe1'
    f2 = load(f2root/'report.json')
    prior_path = base/'F2_idle_observation_v1/audit1/report.json'
    prior = load(prior_path)
    assert sha(prior_path) == f2['prior_observation_report_sha256']
    plan = load(repo/'research/F2_period_relation_v1_plan.json')
    assert len(f2['cases']) == len(prior['display_only_low_band_peaks']) == 3
    for row, source in zip(f2['cases'], prior['display_only_low_band_peaks']):
        assert row['all5_observed_peak_bins_Hz'] == source['L_native1Hz_peak_bins_Hz']
        assert row['source_seconds'] == source['source_seconds']
        for name, spec in plan['hypotheses'].items():
            same(exact_relations(row['all5_observed_peak_bins_Hz'][:3], spec['anchor_orders'],
                                row['all5_observed_peak_bins_Hz'][3:], .5), row['hypotheses'][name])
    specs = [
        ('integer_harmonics_smaller_base_ambiguous', [75,112.5,187.5], [37.5], .01, [True,True]),
        ('fifth_grid_extra_line', [75,112.5,187.5], [82.5,37.5], .01, [False,True]),
        ('independent_extra_line', [75,112.5,187.5], [82.1,37.5], .01, [False,False]),
        ('missing_fundamental_ambiguous', [75,112.5,187.5], [], .01, [True,True]),
        ('inconsistent_anchors', [75,112.5,190], [], .01, [False,False]),
        ('unrelated_frequency_list', [63,101,179], [], .01, [False,False]),
        ('rounded_bin_boundary', [75,112,188], [82,37], .5, [False,True])]
    assert len(f2['controls']['cases']) == len(specs) == 7
    for saved, (name, anchors, extras, width, expected) in zip(f2['controls']['cases'], specs):
        computed = [exact_relations(anchors, orders, extras, width) for orders in ([2,3,5],[10,15,25])]
        assert name == saved['id'] and [x['compatible'] for x in computed] == expected
        same(computed, saved['results'])
    assert f2['selected_fundamental'] is None and not f2['RPM_inferred']
    print('F2 exact rational intersections and all7 controls verified', flush=True)

    f3 = base / 'F3_display_continuity_v1'
    raw, outline = [load(f3/p/'report.json') for p in ('inspect2','shape1')]
    assert sha(f3/'inspect2/report.json') == outline['parent_report_sha256']
    catalogue = load(args.workspace/'references/segments_v1.json')
    assert sha(args.workspace/catalogue['sources']['F3']['video']) == raw['input_sha256']
    assert sha(base/'state_media_v1/F3_context1/report.json') == raw['source_context_sha256']
    templates = {str(r['gear']):image_mask(f3/'inspect2',r['capture']['frames'][0],True) for r in raw['templates']}
    wide = {k:widened(v) for k,v in templates.items()}
    blank = np.zeros_like(templates['5'])
    broken = templates['5'].copy(); broken[:broken.shape[0]//2] = False
    shift = np.zeros_like(blank); shift[:,1:] = templates['5'][:,:-1]
    controls = {'blank':blank,'union_4_5':templates['4']|templates['5'],
                'half_outline_missing':broken,'one_pixel_shift':shift}
    for saved in raw['controls']:
        mask = image_mask(f3/'inspect2',saved['capture']['frames'][0],True) if 'capture' in saved else controls[saved['id']]
        same(scores(mask, templates, wide, False), saved['observed'])
    scalar_error = 0.
    for saved in outline['controls']:
        if 'source_capture' in saved:
            mask = image_mask(f3/'inspect2',saved['source_capture']['frames'][0],True)
        elif saved['id'].startswith('new_native_probe_'):
            gear = int(saved['id'].split('_')[-1])
            capture = next(x for x in outline['new_probe_captures'] if x['gear'] == gear)
            mask = image_mask(f3/'shape1',capture['frame'],True)
            log = (f3/'shape1'/('probe_'+str(gear))/'decode_log.txt').read_text()
            pts = [int(x) for x in re.findall(r'\bn:\s*\d+ pts:\s*(-?\d+) pts_time:',log)]
            assert pts == [capture['frame']['pts']]
        else:
            mask = controls[saved['id']]
        observed = scores(mask, templates, wide, True)
        same(observed, saved['observed'])
        assert (observed['displayed_gear'] == saved['expected']) == saved['passed']
        for k, template in templates.items():
            scalar_error = max(scalar_error, abs(scalar_shape(mask,template)-observed['all_shape_scores'][k]))
    assert scalar_error <= 1e-12
    assert not raw['detector_controls_passed'] and outline['detector_controls_passed']
    windows = {}
    for name, old in raw['windows'].items():
        new = outline['windows'][name]
        assert len(old['frames']) == len(new['frames'])
        log_path = f3/'inspect2'/name/'decode_log.txt'
        log_pts = [int(x) for x in re.findall(r'\bn:\s*\d+ pts:\s*(-?\d+) pts_time:',log_path.read_text())]
        assert log_pts == [r['pts'] for r in old['frames']]
        start = old['frames'][0]['pts']
        expected_start = {'first':158000,'second':189000}[name]
        assert start == expected_start
        for i, (a,b) in enumerate(zip(old['frames'],new['frames'])):
            assert all(a[k] == b[k] for k in ('file','sha256','pts','source_pts_seconds'))
            assert a['source_pts_seconds'] == a['pts']/1000
            assert abs(Q(a['pts']-start,1000)*60-i) <= Q(1,50)
            mask = image_mask(f3/'inspect2',a)
            same(scores(mask,templates,wide,False), {k:a[k] for k in ('displayed_gear','best_template','best_Dice','margin','all_Dice')})
            same(scores(mask,templates,wide,True), {k:b[k] for k in ('displayed_gear','best_template','best_shape_score','margin','all_shape_scores','raw_Dice','all_raw_Dice')})
        runs=[]
        for i,row in enumerate(new['frames']):
            if i == 0 or row['displayed_gear'] != new['frames'][i-1]['displayed_gear']:
                runs.append(dict(start_pts=row['pts'], displayed_gear=row['displayed_gear'], frames=1))
            else: runs[-1]['frames'] += 1
        windows[name] = dict(frames=len(new['frames']), unknown=sum(x['displayed_gear'] is None for x in new['frames']), runs=runs)
        print('F3 both detectors independently replayed: '+name,flush=True)
    for row in outline['candidates']:
        a,b=row['seconds']; rows=[x for w in outline['windows'].values() for x in w['frames'] if a <= x['source_pts_seconds'] < b]
        assert len(rows) == row['frames'] == (b-a)*60
        assert all(x['displayed_gear'] == row['displayed_gear'] for x in rows)
        assert row['unknown_frames'] == 0 and row['all_frames_match_displayed_gear']
    failed=load(f3/'inspect1/report.json'); termination=load(f3/'inspect1/termination_context.json')
    assert failed['result'] == 'failed' and termination['original_report_preserved']
    assert not termination['natural_source_decode_failure_claimed']
    variants={}
    locations={'F2':f2root,'failed_decode':f3/'inspect1','raw_Dice':f3/'inspect2','outline':f3/'shape1'}
    for name,root in locations.items():
        value=load(root/'report.json')
        for relative,digest in value['sources'].items():
            assert sha(root/'exact_sources'/relative) == digest
            variants.setdefault(relative,{})[name]=digest
            if name != 'failed_decode': assert sha(repo/relative)==digest
    old_source=(f3/'inspect1/exact_sources/tools/inspect_F3_display_continuity_v1.py').read_text()
    new_source=(f3/'inspect2/exact_sources/tools/inspect_F3_display_continuity_v1.py').read_text()
    assert "'-frames:v'" not in old_source and "'-frames:v'" in new_source
    assert 'format=rgb24' not in old_source and 'format=rgb24' in new_source
    target=args.out/'exact_sources/tools';target.mkdir(parents=True)
    shutil.copy2(__file__,target/Path(__file__).name)
    report['sources']['tools/'+Path(__file__).name]=sha(Path(__file__))
    report.update(result='F2_exact_intervals_and_all1080_F3_native_frame_classifications_independently_verified',
        F2_report_sha256=sha(f2root/'report.json'),F2_all3_cases_and7_controls_exact_rational=True,
        F2_selected_fundamental=None,RPM_inferred=False,
        F3_raw_report_sha256=sha(f3/'inspect2/report.json'),F3_shape_report_sha256=sha(f3/'shape1/report.json'),
        rejected_Dice_control_reproduced=True,all1080_classifications_reproduced=True,
        independent_PIL_and_scalar_shape_error=scalar_error,windows=windows,candidates=outline['candidates'],
        original_decode_failure_intentional_termination_retained=True,source_variants=variants,
        visually_reviewed=['shape1/probe_'+str(x)+'/frame.png' for x in (4,5,6,7)]+[
            'shape1/'+s['file'] for w in outline['windows'].values() for s in w['review_sheets']],
        visual_scope='Four full native probe frames and four paginated boundary/unknown/worst-match sheets; not every frame manually inspected',
        physical_shift_timing_established=False,AV_delay_calibrated=False,load_inferred=False,
        limits=['Display evidence limited to specified source intervals; animated unknowns remain outside candidates',
                'Frequency boxes are exploratory rounding assumptions, not physical frequency confidence or engine/wind separation',
                'No real phase-extracted DNA, new audio or runtime/C changes'])
    print(json.dumps(dict(result=report['result'],windows=windows,scalar_error=scalar_error)),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc));raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
