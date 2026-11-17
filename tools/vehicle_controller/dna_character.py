"""Shared, serializable DNA voicing contract for the app and recipe workbench."""
from copy import deepcopy
import math

STATES=('启动／接火','怠速','加速／补油','巡航','收油／断火','高转速区')
FIELDS=(('line','进气感声线',0,2.6),('air','排气空气感纹理',0,2.6),
        ('motion','声线自然起伏',0,1.3),('idle_blend','细谱指纹参与量',0,1.3),
        ('air_continuity','高转纹理保留',0,1.3),('pitch_follow','指纹声线随转速',0,1.3))

def defaults():
    return dict(line=1.,air=1.,motion=.5,idle_blend=1.,air_continuity=.35,pitch_follow=.25,
                line_state=[1.]*6,air_state=[1.]*6)

def validate(value):
    if not isinstance(value,dict) or set(value)!={k for k,*_ in FIELDS}|{'line_state','air_state'}:
        raise ValueError('DNA声线／纹理配方字段不完整')
    def number(x,maximum):
        if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not 0<=x<=maximum:
            raise ValueError('DNA配方参数超出范围')
    for key,_,_,maximum in FIELDS:number(value[key],maximum)
    for key in ('line_state','air_state'):
        if not isinstance(value[key],list) or len(value[key])!=6:raise ValueError('DNA需要六组工况响应')
        for x in value[key]:number(x,2.6)
    return deepcopy(value)
