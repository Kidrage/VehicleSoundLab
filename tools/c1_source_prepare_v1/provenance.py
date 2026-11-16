"""Bind existing qualified data and immutable namespaces without launching fits."""
from pathlib import Path
from research_archive_v1 import load, sha


class Proofs:
    def __init__(self, workspace, repo, report):
        self.workspace, self.repo, self.report = workspace, repo, report

    def bind(self, path):
        path = Path(path); self.report['inputs'][str(path)] = sha(path)
        return path

    def read(self, path):
        return load(self.bind(path))

    def absorb(self, value):
        for name, expected in value.get('sources', {}).items():
            assert sha(self.repo/name) == expected, name
            self.report['sources'][name] = expected
        for name, expected in value.get('inputs', {}).items():
            assert sha(name) == expected, name
            self.report['inputs'][name] = expected

    def prerequisites(self):
        base = self.workspace/'references/analysis'
        parent = base/'c1_source_adapter_v1'
        known = self.read(parent/'known1/report.json')
        audit = self.read(parent/'known_audit1/report.json')
        assert known['result'] == 'c1_source_known_measured' and known['all_qualified']
        assert audit['result'] == 'independent_c1_source_known_verified' and audit['verification_passed'] and audit['all_qualified']
        assert audit['producer_sha256'] == sha(parent/'known1/report.json')
        sampling = self.read(parent/'sampling_known1/report.json')
        sa = self.read(parent/'sampling_known_audit1/report.json')
        assert sampling['result'] == 'c1_sampling_known_measured' and sampling['all_qualified']
        assert sa['result'] == 'independent_c1_sampling_known_verified' and sa['verification_passed'] and sa['all_qualified']
        assert sa['producer_sha256'] == sha(parent/'sampling_known1/report.json')
        for value in (known, audit, sampling, sa): self.absorb(value)
        old_root = base/'waveform_file_real_v1'
        original = self.read(old_root/'prepare1/report.json')
        oa = self.read(old_root/'prepare_audit1/report.json')
        assert original['result'] == 'waveform_file_real_six_prepared' and len(original['cases']) == 6
        assert oa['all_qualified'] and oa['producer_sha256'] == sha(old_root/'prepare1/report.json')
        context = self.read(base/'recorded_phase_context_v1/real1/report.json')
        ca = self.read(base/'recorded_phase_context_v1/real_audit1/report.json')
        assert ca['all_qualified'] and ca['producer_sha256'] == sha(base/'recorded_phase_context_v1/real1/report.json')
        self.absorb(original)
        self.report['prerequisites_independently_qualified'] = True
        return original, context

    def protect(self, label):
        assert label == 'F3 Fifth First Late'
        base = self.workspace/'references/analysis'; namespaces = []
        for name, counts in (('waveform_file_real_v1', (96, 71)), ('locked_source_fit_v1', (124, 101))):
            root = base/name/'real1'; spec = self.read(root/'run_spec.json')
            assert (len(spec['sources']), len(spec['inputs'])) == counts
            self.absorb(spec)
            state = self.read(root/'report.json'); assert state['result'] == 'failed'
            assert state.get('current_case') != label
            assert all(row.get('label') != label for row in state.get('cases', []))
            assert not (root/label).exists() and not (root/(label+'_audit')).exists()
            namespaces.append(dict(root=str(root), report_result=state['result'], selected_label_absent=True,
                existing_directories=sorted(p.name for p in root.iterdir() if p.is_dir())))
        conditional_path = base/'locked_source_diagnostics_followthrough_v1/manifest.json'
        conditional = self.read(conditional_path)
        assert len(conditional['source_sha256']) == 151
        assert conditional['run_spec_sha256'] == sha(base/'locked_source_fit_v1/real1/run_spec.json')
        for path, expected in conditional['source_sha256'].items():
            assert sha(path) == expected
            path = Path(path)
            if path.is_relative_to(self.repo): self.report['sources'][path.relative_to(self.repo).as_posix()] = expected
            else: self.report['inputs'][str(path)] = expected
        previous = load(self.repo/'research/clock_native_bridge_v1_summary.json')
        for name, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
            values = self.read(self.workspace/'baselines/clock_native_bridge_v1/evidence'/name)
            assert len(values) == count
            for path, expected in values.items(): assert sha(self.repo/path) == expected
        assert sha(self.repo/'handoff/C文件索引.csv') == previous['protected_C_index_sha256']
        for path, expected in previous['protected_hearings_sha256'].items(): assert sha(self.repo/path) == expected
        d_root = Path('D:/VehicleSoundLab-Work/source_fit_storage_v1')
        assert d_root.is_dir()
        d_specs = sorted(d_root.rglob('run_spec.json')); assert not d_specs
        return dict(label=label, scope='No prior full-waveform file fit in original/current canonical namespaces',
            namespaces=namespaces, D_storage_root=str(d_root), D_run_specs=[],
            D_root_entries=sorted(p.name for p in d_root.iterdir()),
            original124sources101inputs151conditionalbindings_verified=True,
            protected670C_H82voice3F2_index_and_hearings=True,
            future_cross_drive_registration_not_implemented=True)
