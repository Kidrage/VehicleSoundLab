"""Package approved-source authored parameters, never original PCM, for the App."""
import hashlib,json,shutil
from pathlib import Path
def main():
    repo=Path(__file__).resolve().parents[1];source=Path('E:/VehicleSoundLab/references/analysis/startup_rotation_v1/listen2')
    dest=repo/'experiments/startup_character_v1/runtime_bank';dest.mkdir(exist_ok=False)
    profiles={}
    for name,folder in (('prelude','old-prelude'),('crank','.'),('catch','old-catch'),('previous','old-crank')):
        path=source/'model'/folder/'profile.json';doc=json.loads(path.read_text(encoding='utf-8'));out=dest/name;out.mkdir()
        for row in doc['profiles']:
            target=out/Path(row['path']).name;shutil.copy2(row['path'],target);row['path']=target.relative_to(dest).as_posix()
        profiles[name]=doc
    recipe=json.loads((source/'recipe.json').read_text(encoding='utf-8'));control=json.loads((source/'control.json').read_text(encoding='utf-8'))
    bank=dict(schema='vsl.startup-audition-bank/1',profiles=profiles,recipe=recipe,base=control,source='Approved A exterior; authored procedural parameters, no original PCM',human_accepted=False)
    (dest/'bank.json').write_text(json.dumps(bank,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest=[dict(path=p.relative_to(dest).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(dest.rglob('*')) if p.is_file()]
    (dest/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(dict(files=len(manifest),bytes=sum(p.stat().st_size for p in dest.rglob('*') if p.is_file())))
if __name__=='__main__':main()
