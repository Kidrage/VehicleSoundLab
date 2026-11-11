from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
times=[10,34,60,100,130,180,210,240,270,297,318,332]
folder=ROOT/'references/analysis/context_frames';folder.mkdir(exist_ok=True)
def extract(t):
    subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-ss',str(t),'-i',str(ROOT/'references/raw/A_context_360p.mp4'),
        '-frames:v','1','-q:v','2',str(folder/f'{t}.jpg')],check=True)
with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(extract,times))
board=Image.new('RGB',(1280,4*390),(20,25,34));draw=ImageDraw.Draw(board)
font=ImageFont.truetype(r'C:\Windows\Fonts\segoeui.ttf',20)
for i,t in enumerate(times):
    im=Image.open(folder/f'{t}.jpg').resize((426,240));x=i%3*426;y=i//3*390
    board.paste(im,(x,y));draw.text((x+10,y+250),f'A / source {t:03d} seconds',font=font,fill='white')
board.save(ROOT/'references/analysis/A_context_sheet.jpg')
