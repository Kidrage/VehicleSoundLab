"""Additional native frames for conservative scene/gear evidence, no RPM fit."""
import json, subprocess
from runtime_review import ROOT, sha
from PIL import Image, ImageDraw, ImageFont

OUT=ROOT/'references/analysis/DE_details_v1'
def main():
    if OUT.exists(): raise SystemExit('Keep completed observations; use a new directory.')
    OUT.mkdir()
    result={}
    for source,seconds in [('D',[12,20,26,28,30,32,40,48]),('E',[45,47,55,58,74,77,82,84,86,88,90,94,100,106,112,118])]:
        index=json.loads((ROOT/f'references/analysis/DE_usability_v1/{source}/video_frames.json').read_text())
        frames=index['all_frames']; rows=[]
        raw=next((ROOT/'references/raw').glob(source+'_*.mkv'))
        for t in seconds:
            n=min(range(len(frames)),key=lambda i:abs(float(frames[i]['best_effort_timestamp_time'])-t))
            path=OUT/f'{source}_{t:03}.png'
            subprocess.run([r'D:\repo\tools\ffmpeg\bin\ffmpeg.exe','-nostdin','-v','error','-n','-i',str(raw),'-vf',f'select=eq(n\\,{n})','-frames:v','1',str(path)],check=True,capture_output=True)
            rows.append(dict(requested_seconds=t,index=n,pts=int(frames[n]['best_effort_timestamp']),time_base=index['time_base'],pts_seconds=float(frames[n]['best_effort_timestamp_time']),file=path.name,sha256=sha(path)))
        board=Image.new('RGB',(1600,248*((len(rows)+3)//4)),(18,28,35));d=ImageDraw.Draw(board)
        font=ImageFont.truetype(r'C:\Windows\Fonts\consola.ttf',15)
        for i,row in enumerate(rows):
            with Image.open(OUT/row['file']) as im:
                im.thumbnail((400,225));x=i%4*400;y=i//4*248
                board.paste(im,(x,y));d.text((x+5,y+225),f"{source} n={row['index']} PTS={row['pts_seconds']:.3f}",font=font,fill='white')
        board.save(OUT/f'{source}_overview.jpg',quality=94);result[source]=rows
    (OUT/'frames.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
if __name__=='__main__':main()
