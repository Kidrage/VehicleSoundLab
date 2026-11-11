import html
import re
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
root=Path(__file__).resolve().parents[1]
for name in ('spectral_modeling_synthesis.html','sinusoidal_modeling.html','designing_sound.html'):
    raw=(root/'research'/name).read_text(encoding='utf-8',errors='replace')
    raw=re.sub(r'<(script|style)\b.*?</\1>',' ',raw,flags=re.S)
    text=html.unescape(re.sub('<[^>]+>',' ',raw))
    text=re.sub(r'\s+',' ',text)
    print(name,text[:13000],'\n')
