"""One native raster pixel of symmetric outline coverage; raw Dice remains separate."""
import numpy as np


def expanded(mask):
    pad=np.pad(mask,1)
    return np.logical_or.reduce([pad[y:y+mask.shape[0],x:x+mask.shape[1]] for y in range(3) for x in range(3)])


def classify(mask,templates):
    widened=expanded(mask)
    scores={};dice={}
    count=np.count_nonzero(mask)
    for key,value in templates.items():
        total=np.count_nonzero(value)
        scores[key]=float(.5*(np.count_nonzero(mask&expanded(value))/count+
            np.count_nonzero(value&widened)/total)) if count and total else 0.
        dice[key]=float(2*np.count_nonzero(mask&value)/(count+total)) if count+total else 0.
    ordered=sorted(scores,key=lambda key:scores[key],reverse=True)
    best,second=ordered[:2];margin=scores[best]-scores[second]
    label=int(best) if scores[best]>=.90 and margin>=.10 else None
    return dict(displayed_gear=label,best_template=int(best),best_shape_score=scores[best],
        margin=margin,all_shape_scores=scores,raw_Dice=dice[best],all_raw_Dice=dice)
