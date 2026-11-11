"""Publish the bounded findings of the second-passage shift comparison."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

root = args.workspace / 'references/analysis/shift_repeat_v1'
exploration = json.loads((root / 'exploration1/report.json').read_text(encoding='utf-8'))
analysis = json.loads((root / 'analysis1/report.json').read_text(encoding='utf-8'))
verification = json.loads((root / 'verification1/verification.json').read_text(encoding='utf-8'))
assert verification['result'] == 'pass'
assert verification['analysis_sha256'] == sha(root / 'analysis1/report.json')
assert analysis['exploration_sha256'] == sha(root / 'exploration1/report.json')
assert analysis['annotation_sha256'] == sha(repo / 'research/shift_repeat_v1_annotations.json')
assert not analysis['runtime_changed'] and not verification['runtime_changed']
assert not verification['common_shift_profile_promoted']
metadata = {
    'references/segments_v1.json': analysis['provenance']['catalog_sha256'],
    'references/analysis/DE_usability_v1/E/video_frames.json': exploration['index_sha256'],
    'references/approval_manifest.json': sha(args.workspace / 'references/approval_manifest.json')}
for name, digest in metadata.items():
    assert sha(args.workspace / name) == digest, name

for folder, report in (('analysis1', analysis), ('verification1', verification)):
    for name, digest in report['source_sha256'].items():
        assert sha(root / folder / 'exact_sources' / name) == digest, name

# The exploration comment previously implied an unimplemented spectral check.
# Preserve the executed bytes, and require the published correction to be AST-identical.
name = 'tools/explore_shift_repeat_v1.py'
executed = root / 'analysis1/exact_sources' / name
assert sha(executed) == exploration['source_sha256'][name]
assert ast.dump(ast.parse(executed.read_text(encoding='utf-8'))) == ast.dump(
    ast.parse((repo / name).read_text(encoding='utf-8')))
for name, digest in analysis['source_sha256'].items():
    if name != 'tools/explore_shift_repeat_v1.py':
        assert sha(repo / name) == digest, name

plot = repo / 'research/shift_repeat_v1_comparison.png'
shutil.copy2(root / 'analysis1/passage_comparison.png', plot)
source_names = sorted(set(analysis['source_sha256']) | set(verification['source_sha256']) | {
    'tools/summarize_shift_repeat_v1.py', 'tools/freeze_shift_repeat_v1.py'})
evidence = sorted(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
summary = dict(
    schema='vsl.shift-repeat-summary/1',
    date='2026-11-12',
    base_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    result='pass',
    result_scope='Input identity, direct FFT and known controls pass; not a universal shift profile or real-clock qualification',
    evidence_root=str(root),
    input_metadata_sha256=metadata,
    provenance=analysis['provenance'],
    frames=len(exploration['frames']),
    gear_display_changes=json.loads((repo / 'research/shift_repeat_v1_annotations.json').read_text(encoding='utf-8'))['gear_display_changes'],
    acoustic_markers_seconds=[e['marker_seconds'] for e in analysis['analyses'][0]['events']],
    shape_reference_band_relative_root=[6.5, 18.5],
    shape_bands_relative_root=[[18.5, 45.5], [45.5, 110.5]],
    old_shape_db=analysis['old_shape_db'],
    new_shape_db=analysis['new_shape_db'],
    previous_median_prediction_error_db=analysis['heldout_first_passage_error_db'],
    known_control_max_error_db=verification['known_control_max_db'],
    direct_fft_max_absolute_error=verification['direct_fft_max_absolute_error'],
    clock_sensitivity=[dict(marker=e['marker'], minimum_db=e['minimum_db'], maximum_db=e['maximum_db'])
                       for e in verification['clock_sensitivity']],
    window_sensitivity=verification['window_sensitivity'],
    sensitivity_interpretation='Engineering +/-2% perturbations, not measured clock confidence. Second shift highest band spans zero.',
    waveform_duplicate_check=exploration['duplicate_audio_diagnostic'],
    upstream_revision=analysis['upstream_revision'],
    c_index_rows=verification['c_index_rows'],
    c_index_sha256=verification['c_index_sha256'],
    executed_analysis_sources=analysis['source_sha256'],
    executed_verification_sources=verification['source_sha256'],
    publication_change='Exploration comment corrected only; AST matches archived executed source. No spectral duplication check was run.',
    source_sha256={name: sha(repo / name) for name in source_names},
    evidence_sha256={p.relative_to(root).as_posix(): sha(p) for p in evidence},
    plot_sha256=sha(plot),
    runtime_changes=False, human_accepted=False, common_shift_profile_promoted=False,
    limits=analysis['limits'] + verification['limits'])
target = repo / 'research/shift_repeat_v1_summary.json'
target.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print(json.dumps(dict(path=str(target), evidence_files=len(evidence), result=summary['result']), ensure_ascii=False))
