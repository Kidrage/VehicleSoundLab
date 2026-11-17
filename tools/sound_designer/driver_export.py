"""Compile an edited workbench model into the portable controller contract."""
import json
from vehicle_controller import dna_bank


def write(output,model_file,name,reference_rpm,controls,provenance):
    bank=dna_bank.create([dna_bank.anchor(model_file.read_text(encoding='ascii'),name)],
        reference_rpm,name,controls['seed'],12,controls['detail'])
    (output/'driver.dnabank.json').write_text(json.dumps(bank,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    report=dict(schema='vsl.driver-dna-export/1',dna_bank_sha256=dna_bank.digest(bank),
        model_sha256=bank['anchors'][0]['sha256'],reference_rpm=reference_rpm,
        mapping='User-supplied engineering RPM mapping, not measured ECU RPM.',
        coverage='Single-state DNA anchor; no load/state timbre calibration or physical source separation.',
        gain_policy='Workbench gain/width/EQ/shared/local are baked in model coefficients; controller master gain remains independently adjustable.',
        detail=controls['detail'],preview_pitch=controls['pitch'],
        pitch_policy='Preview pitch is not baked in; controller root Hz follows the explicit reference-RPM mapping.',
        optional_layers='No catalog LF, resonance, residual, idle, start or catch textures; auxiliary/event layers initially off.',
        provenance=provenance)
    (output/'driver-provenance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    return report
