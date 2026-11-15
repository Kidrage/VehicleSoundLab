"""Signed changes and explicit undefined ratios; never a listening score."""
import numpy as np


def ratio_array(numerator,denominator,*,db=False):
    a,b=np.broadcast_arrays(np.asarray(numerator),np.asarray(denominator))
    result=[]
    for x,y in zip(a.ravel(),b.ravel()):
        if y<=0 or (db and x<=0):result.append(None)
        else:result.append(float(10*np.log10(x/y) if db else x/y))
    return np.array(result,dtype=object).reshape(a.shape).tolist()


def compare(candidate,reference):
    result={}
    for prefix in ('broad','line'):
        if prefix+'_mean_power' not in reference:continue
        if prefix+'_mean_power' not in candidate:raise ValueError('Missing candidate line diagnostic')
        row=dict(power_change_dB=ratio_array(candidate[prefix+'_mean_power'],reference[prefix+'_mean_power'],db=True),
            mid_side_change_dB=ratio_array(candidate[prefix+'_mean_mid_side'],reference[prefix+'_mean_mid_side'],db=True),
            power_change_FS2=(candidate[prefix+'_mean_power']-reference[prefix+'_mean_power']).tolist(),
            mid_side_change_FS2=(candidate[prefix+'_mean_mid_side']-reference[prefix+'_mean_mid_side']).tolist())
        for field in ('CV','complex_coherence'):
            mask=reference[prefix+('_power_defined' if field=='CV' else '_coherence_defined')] & candidate[prefix+('_power_defined' if field=='CV' else '_coherence_defined')]
            delta=candidate[prefix+'_'+field]-reference[prefix+'_'+field]
            if np.iscomplexobj(delta):
                row[field+'_change']=[([float(v.real),float(v.imag)] if good else None) for v,good in zip(delta,mask)]
            else:row[field+'_change']=np.where(mask,delta,None).tolist()
        for field in ('covariance','lag_covariance'):
            delta=candidate[prefix+'_'+field]-reference[prefix+'_'+field]
            row[field+'_signed_change_FS4']=delta.tolist()
            den=float(np.linalg.norm(reference[prefix+'_'+field]))
            row[field+'_relative_difference']=float(np.linalg.norm(delta)/den) if den else None
        result[prefix]=row
    return result
