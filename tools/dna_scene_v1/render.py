"""Offline C probe invocation and artifact provenance, never audio synthesis."""
import hashlib
import json
import subprocess
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make(repository, output, probe, seconds):
    acceptance_path = repository / 'research/coherent_low_v1_acceptance.json'
    acceptance = json.loads(acceptance_path.read_text(encoding='utf-8'))
    dna = repository / 'voices/dna_bank_v1/V10 Exterior.model'
    low = repository / acceptance['model']
    assert sha(dna) == acceptance['dna_model_sha256']
    assert sha(low) == acceptance['model_sha256']
    cases = [
        ('pair_dry', dna, low, {}),
        ('pair_room', dna, low, {'space': .65}),
        ('pair_geometry', dna, low, {'propagation': 1}),
        ('left_geometry', dna, low, {'propagation': 1, 'route': 'left'}),
        ('right_geometry', dna, low, {'propagation': 1, 'route': 'right'}),
        ('bed_dry', dna, low, {'channels': 12}),
        ('bed_room', dna, low, {'channels': 12, 'space': .65}),
        ('warm', repository / 'voices/dna_bank_v1/Warm Additive.model', None, {}),
        ('hollow', repository / 'voices/dna_bank_v1/Hollow Spectrum.model', None, {})
    ]
    directory = output / 'raw'
    directory.mkdir()
    records = {}
    for name, model, supplement, override in cases:
        settings = dict(seconds=seconds, channels=2, pitch=1, dna=1,
                        low=1, low_scale=acceptance['low_scale'], detail=1,
                        low_detail=1, gain=.5, width=1, space=0,
                        perspective=0, propagation=0, route='pair', projection='left')
        settings.update(override)
        command = [str(probe), str(model), str(supplement) if supplement else '-', str(directory / name)]
        for key, value in settings.items():
            command.extend(['--' + key.replace('_', '-'), str(value)])
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=180)
        records[name] = dict(settings=settings, command=command,
                             probe=json.loads(result.stdout), dna_sha256=sha(model),
                             low_sha256=sha(supplement) if supplement else None)
        print(json.dumps(dict(render=name, **records[name]['probe'])), flush=True)
    return records
