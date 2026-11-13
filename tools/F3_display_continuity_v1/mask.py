"""Fixed native-pixel orange segmentation and conservative template agreement."""
import numpy as np


def orange(rgb):
    values=np.asarray(rgb,dtype=float)
    red,green,blue=values[:,:,0],values[:,:,1],values[:,:,2]
    return (red>150)&(green>80)&(blue<100)&(red>1.1*green)


def classify(mask,templates):
    scores={key:float(2*np.count_nonzero(mask&value)/(np.count_nonzero(mask)+np.count_nonzero(value)))
            for key,value in templates.items()}
    ordered=sorted(scores,key=lambda key:scores[key],reverse=True)
    best,second=ordered[:2]
    margin=scores[best]-scores[second]
    label=int(best) if scores[best]>=.90 and margin>=.10 else None
    return dict(displayed_gear=label,best_template=int(best),best_Dice=scores[best],
                margin=margin,all_Dice=scores)
