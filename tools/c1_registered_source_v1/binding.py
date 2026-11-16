"""Immutable registration/execution bindings and original protected contracts."""
from pathlib import Path
import sys
from research_archive_v1 import load, sha
from c1_fit_registration_v1.registry import verify_pair


REGISTRATION_SHA = '804ef7eb23b1185f743629175e80d14790e15c232236eb1cfe8f5a224f88675b'


def protected(workspace, repo):
    base = workspace/'baselines/c1_fit_registration_v1'
    for filename, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        values = load(base/'evidence'/filename)
        assert len(values) == count
        for name, expected in values.items():
            assert sha(repo/name) == expected
    guard = load(base/'validation.json')
    assert sha(repo/'handoff/C文件索引.csv') == guard['protected_C_index_sha256']
    for name, expected in guard['protected_hearings_sha256'].items():
        assert sha(repo/name) == expected


def registration(workspace, repo):
    report = load(workspace/'references/analysis/c1_fit_registration_v1/registration1/report.json')
    audit = load(workspace/'references/analysis/c1_fit_registration_v1/registration_audit1/report.json')
    assert report['result'] == 'c1_source_single_registration_reserved'
    assert audit['verification_passed'] and audit['producer_sha256'] == sha(workspace/'references/analysis/c1_fit_registration_v1/registration1/report.json')
    original = report['pair']['spec']
    e, d = Path(original['canonical_claim']), Path(original['storage_claim'])
    pair = verify_pair(e, d)
    assert pair['spec'] == original and pair['registration_sha256'] == REGISTRATION_SHA
    assert e.drive.upper() == 'E:' and d.drive.upper() == 'D:'
    assert original['original_label'] == 'F3 Fifth First Late'
    for name, expected in original['source_closure'].items():
        assert sha(repo/name) == sha(Path(original['exact_sources_root'])/name) == expected
    for name, expected in original['input_closure'].items():
        assert sha(name) == expected
    for name, expected in original['toolchain']['native_files_sha256'].items():
        assert sha(name) == expected
    assert Path(sys.executable).resolve() == Path(original['toolchain']['python_executable']).resolve()
    assert sys.version == original['toolchain']['python']
    for item in original['legacy_namespace_snapshot']['namespaces']:
        root = Path(item['root'])
        assert load(root/'report.json')['result'] == 'failed'
        assert sorted(p.name for p in root.iterdir() if p.is_dir()) == item['existing_directories']
    protected(workspace, repo)
    return pair


def execution(workspace, repo, *, require_unlaunched=False):
    pair = registration(workspace, repo)
    original = pair['spec']
    e, d = Path(original['canonical_claim']), Path(original['storage_claim'])
    assert (e/'execution_spec.json').read_bytes() == (d/'execution_spec.json').read_bytes()
    spec = load(e/'execution_spec.json')
    assert spec['schema'] == 'vsl.c1-registered-source-execution/1'
    assert spec['registration_sha256'] == REGISTRATION_SHA
    assert spec['source_identity'] == original['source_identity']
    assert spec['measurement_identity'] == original['measurement_identity']
    assert spec['only_label'] == original['original_label']
    assert spec['geometry'] == original['geometry'] and spec['block'] == 1024
    assert Path(spec['output']).resolve() == (d/'run1').resolve()
    assert spec['input_file'] == original['input_file'] and spec['input_sha256'] == original['input_sha256']
    for name, expected in spec['source_closure'].items():
        assert sha(repo/name) == sha(Path(spec['exact_sources_root'])/name) == expected
    for name, expected in spec['input_closure'].items():
        assert sha(name) == expected
    known = load(spec['terminal_known_audit'])
    assert known['verification_passed'] and known['all_qualified']
    assert (known['full_terminal_cases'], known['exact_zero_cases'], known['corruptions_rejected']) == (3, 1, 6)
    for name, expected in known['sources'].items():
        assert spec['source_closure'][name] == expected
    for name, expected in known['known_factor_files_sha256'].items():
        assert sha(name) == expected
    if require_unlaunched:
        assert not (e/'launch_intent.json').exists() and not (d/'launch_intent.json').exists()
        assert not Path(spec['output']).exists()
    return pair, spec
