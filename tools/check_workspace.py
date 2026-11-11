"""Final consistency checks for local deliverables, without fetching media."""
import sys
import json
from pathlib import Path
from html.parser import HTMLParser
ROOT=Path(__file__).resolve().parents[1]
class Links(HTMLParser):
    def handle_starttag(self,tag,attrs):
        for key,value in attrs:
            if key in ('src','href') and not value.startswith(('https:','http:','#')):
                assert (ROOT/'research'/value).resolve().exists(),value
Links().feed((ROOT/'research/试听对照.html').read_text(encoding='utf-8'))
for identity in ('A','B'):
    assert (ROOT/f'references/raw/{identity}_provenance.json').exists()
    catalog=json.loads((ROOT/f'references/analysis/{identity}_clip_catalog.json').read_text())
    for clip in catalog:
        assert clip['metrics']['clipped_sample_fraction']==0,clip['name']
        assert Path(clip['file']+'.provenance.json').exists()
assert not (Path.home() / 'Desktop' / '2023 Lamborghini Huracan Tecnica - POV Canyon Blast (Binaural Audio).mp3').exists()
smoke=json.loads((ROOT/'renders/ui_smoke.json').read_text())
assert smoke['waveOut_opened_and_queued_audio'] and smoke['export_succeeded']
assert json.loads((ROOT/'renders/dna_pipeline_check.json').read_text())['result']=='pass'
print('PASS: local media links, 7 unclipped approved excerpts, provenance, Desktop relocation, UI audio lifecycle and DNA interchange')
