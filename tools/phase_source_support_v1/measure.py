"""Exact orthogonal-loading accounting; all units are explicit."""
import numpy as np


def shared_pairs(pc,basis):
    n,k=pc.shape
    lengths=np.linalg.norm(basis,axis=0)
    if not np.all(lengths>0):raise ValueError('Nonzero saved PCA columns required')
    unit=basis/lengths
    if not np.allclose(unit.T@unit,np.eye(k),atol=2e-11,rtol=0):
        raise ValueError('Orthogonal saved PCA columns required')
    x=pc-pc.mean(axis=0)
    c=x[1:].T@x[:-1]/(n-1);skew=(c-c.T)/2
    weighted=skew*lengths[:,None]*lengths[None,:]
    indices=[(i,j) for i in range(k) for j in range(i+1,k)]
    energy=np.array([2*weighted[i,j]**2 for i,j in indices]);total=float(energy.sum())
    order=sorted(range(len(indices)),key=lambda at:(-energy[at],indices[at]))
    pairs=[dict(pc_i=indices[at][0],pc_j=indices[at][1],squared_feature_skew_norm=float(energy[at]),
        fraction_of_shared_feature_skew_squared=float(energy[at]/total) if total else None) for at in order]
    leading=pairs[0]
    load=(unit[:,leading['pc_i']]**2+unit[:,leading['pc_j']]**2)/2
    return pairs,load,dict(column_lengths=lengths,unit_basis=unit,pc_lag1=c,weighted_skew=weighted)


def harmonic_load(feature_load):
    h=len(feature_load)//4
    return feature_load[:2*h].reshape(h,2).sum(axis=1)+feature_load[2*h:3*h]+feature_load[3*h:]


def describe(training,profile,positions,root):
    pc=training['pc'];basis=profile['basis'];n=len(pc);h=288
    q=training['source_rows'].reshape(n,h,2,2);z=q[...,0]+1j*q[...,1]
    amplitude=abs(z).reshape(n,2*h)
    if not np.array_equal(amplitude,training['amplitude']):raise ValueError('Saved amplitude mismatch')
    common,relative=training['coordinates'][:,:h],training['coordinates'][:,h:]
    phase=np.stack((common+.5*relative,common-.5*relative),axis=-1)
    if abs(amplitude.reshape(n,h,2)*np.exp(1j*phase)-z).max()>2e-12:
        raise ValueError('Saved common/relative coordinates do not roundtrip')
    pairs,feature,arrays=shared_pairs(pc,basis);load=harmonic_load(feature)
    mean_power=.5*np.mean(np.sum(abs(z)**2,axis=2),axis=0)
    centred=z-z.mean(axis=0)
    variation_power=.5*np.mean(np.sum(abs(centred)**2,axis=2),axis=0)
    top=np.array(sorted(range(h),key=lambda i:(-load[i],i))[:8])
    strongest=np.array(sorted(range(h),key=lambda i:(-variation_power[i],i))[:8])
    starts=np.arange(0,len(positions)-4096+1,256)
    if len(starts)!=n:raise ValueError('Source query count does not match original rows')
    centers=positions[starts+2048]
    spans=positions[starts+4095]-positions[starts]
    root_estimate=2/(1024*(positions[starts+2049]-positions[starts+2047]))
    steps=np.diff(centers)
    group=np.array([feature[np.arange(ch,2*h,2)].sum() for ch in (0,1)]+
        [feature[2*h:3*h].sum(),feature[3*h:].sum()])
    singular=np.linalg.svd(pc[:-1],compute_uv=False)
    meta=dict(rows=n,shared_components=pc.shape[1],feature_width=basis.shape[0],
        coefficient_center_span_seconds=float(centers[-1]-centers[0]),
        original_query_span_seconds=float(positions[-1]-positions[0]),
        maximum_disjoint_windows=len(positions)//4096,
        physical_center_step_seconds_min=float(steps.min()),physical_center_step_seconds_max=float(steps.max()),
        source_window_seconds_min=float(spans.min()),source_window_seconds_max=float(spans.max()),
        observed_acoustic_root_Hz_min=float(root_estimate.min()),observed_acoustic_root_Hz_max=float(root_estimate.max()),
        renderer_root_Hz=float(root),renderer_step_seconds=1/(4*root),
        maximum_center_step_relative_renderer_difference=float(abs(steps*4*root-1).max()),
        past_PC_design_rank=int(np.linalg.matrix_rank(pc[:-1])),
        past_PC_design_condition=float(singular[0]/singular[-1]),
        leading_pair_feature_group_fractions=group.tolist(),
        leading_pair_squared_feature_skew_fraction=pairs[0]['fraction_of_shared_feature_skew_squared'],
        first3_pair_squared_feature_skew_fraction=float(sum(v['fraction_of_shared_feature_skew_squared'] for v in pairs[:3])),
        top8_feature_loading_harmonics=(top+1).tolist(),
        top8_feature_loading_mean_coefficient_power_fraction=float(mean_power[top].sum()/mean_power.sum()),
        top8_feature_loading_variation_coefficient_power_fraction=float(variation_power[top].sum()/variation_power.sum()),
        top8_variation_coefficient_power_harmonics=(strongest+1).tolist(),
        top8_variation_coefficient_power_fraction=float(variation_power[strongest].sum()/variation_power.sum()),
        raw_complex_coordinate_roundtrip_error_FS=float(abs(amplitude.reshape(n,h,2)*np.exp(1j*phase)-z).max()),
        no_mechanical_or_RPM_or_perceptual_or_raw_broadband_energy_claim=True,
        no_independent_temporal_law_identification=True)
    arrays.update(feature_load=feature,harmonic_load=load,source_complex=z,mean_coefficient_power=mean_power,
        variation_coefficient_power=variation_power,window_starts=starts,physical_centers=centers,
        window_spans=spans,observed_root_estimate=root_estimate,past_design_singular_values=singular)
    return pairs,arrays,meta
