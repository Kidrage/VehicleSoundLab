"""Plot the verified idle material and actual runtime coverage observations."""
import argparse
import json
from pathlib import Path
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
args=p.parse_args()
sys.path[:0]=[str(args.workspace/'tools/python_deps')]
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

root=args.workspace/'references/analysis/idle_material_v1'
r=json.loads((root/'observe2/report.json').read_text(encoding='utf-8'))
audit=json.loads((root/'audit1/report.json').read_text(encoding='utf-8'))
assert audit['result']=='all30_native_tiles_and2_literal_fullband_DFTs_verified'
font_manager.fontManager.addfont('C:/Windows/Fonts/msyh.ttc')
plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':10})
fig,axes=plt.subplots(2,1,figsize=(11,8.5),gridspec_kw={'height_ratios':[1.35,1]},layout='constrained')
labels=['30–120','120–400','400–1200','1.2–2.2k','2.2–4k','4–8k','8–14k']
names=['F2 尾排怠速（主参考）','A 低转片段（另机位）','A 驻车低声线（另片段）','E 片头低转（含场景）','当前 Full Recipe 怠速']
colors=['#18754a','#9aa4a9','#c0c7c9','#438eac','#b33c35']
for item,name,color in zip(r['observations'],names,colors):
    p=np.array(item['fraction_of_mean_band_power'])[:,0]
    axes[0].plot(range(7),10*np.log10(np.maximum(p,1e-15)),marker='o',label=name,color=color,linewidth=2 if color in (colors[0],colors[-1]) else 1)
axes[0].set_xticks(range(7),labels)
axes[0].set_ylim(-125,3)
axes[0].set_ylabel('相对 30–14kHz 总频带功率 / dB')
axes[0].set_title('怠速缺口：主 OSC 载频约止于 2.13kHz，连续细节与独立低频未启用',loc='left',fontweight='bold',pad=16)
axes[0].grid(alpha=.2)
axes[0].legend(loc='lower left',fontsize=9)
f2=r['observations'][0];fractions=np.array(f2['per_tile_fraction'])[:,:,0]*100
time=6.25+.5*np.arange(len(fractions))
for index,name,color in [(1,'120–400 Hz','#18754a'),(2,'400–1200 Hz','#527da5'),(3,'1.2–2.2 kHz','#bd8650')]:
    axes[1].plot(time,fractions[:,index],marker='.',label=name,color=color)
axes[1].plot(time,fractions[:,4:].sum(axis=1),marker='.',label='2.2–14 kHz',color='#995a86')
axes[1].set_yscale('log')
axes[1].set_ylim(.35,35)
axes[1].set_xticks(np.arange(6,12.1,1))
axes[1].set_xlabel('F2 原录音时间 / 秒；固定 0.5 秒块，无重新选段')
axes[1].set_ylabel('每块的频带功率占比 / %')
axes[1].set_title('F2：6 秒原声的频带结构持续存在，变化还包含风噪与话筒移动',loc='left',pad=12)
axes[1].grid(alpha=.2,which='both')
axes[1].legend(loc='upper right',ncol=2,fontsize=9)
fig.suptitle('素材提取证据 · 尚未生成新的怠速音色',fontsize=16,fontweight='bold')
args.out.parent.mkdir(parents=True,exist_ok=True)
fig.savefig(args.out,dpi=150)
plt.close(fig)
print(str(args.out))
