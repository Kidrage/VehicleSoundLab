"""Keep superseded diagnostics without confusing them with float-based results."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
destination=root/'references/analysis/superseded_integer_decode'
destination.mkdir(exist_ok=True)
assert destination.resolve().is_relative_to(root.resolve())
for stem in ('A_corsa_tailpipe_idle','A_corsa_tailpipe_blips','A_tailpipe_road_pull','A_engine_bay_texture'):
    for suffix in ('.wav','.wav.provenance.json','.analysis.json'):
        source=root/'references/clean'/(stem+suffix)
        if source.exists():source.rename(destination/source.name)
source=root/'references/clean/A_decoded_48k.wav'
if source.exists():source.rename(destination/source.name)
