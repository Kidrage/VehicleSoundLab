"""One common coordinate with real phase departures on at most a few partials."""
import numpy as np
from aperture_model_v1.basis import spline
from aperture_model_v1.fit import Model


class MinorityModel(Model):
    def __init__(self,time,plan,variant,selected):
        super().__init__(time,plan)
        self.base_count=self.parameter_count
        self.selected=list(selected)
        if len(set(selected))!=len(selected) or any(index<0 or index>=self.parts for index in selected):
            raise ValueError('Invalid departure partial indices')
        if len(selected)>variant['maximum_departure_partials']:
            raise ValueError('Too many independent partials')
        self.departure_basis=spline(time,plan['cycles'],variant['departure_knot_cycles'])
        self.departure_count=self.departure_basis.shape[1]
        self.parameter_count+=len(selected)*self.departure_count

    def samples(self,parameters,jacobian=False):
        count=self.parts
        a=parameters[:count]
        b=parameters[count:2*count]
        p=parameters[2*count:2*count+self.phase_count]
        beta=parameters[2*count+self.phase_count:self.base_count].reshape(count,self.envelope_count)
        phase=self.phase_basis@p
        envelope=1+self.envelope_basis@beta.T
        angle=2*np.pi*(self.time[:,None]+phase[:,None])*self.orders[None,:]
        for position,index in enumerate(self.selected):
            start=self.base_count+position*self.departure_count
            angle[:,index]+=self.departure_basis@parameters[start:start+self.departure_count]
        cosine=np.cos(angle)
        sine=np.sin(angle)
        partial=envelope*(cosine*a+sine*b)
        result=partial.sum(axis=1)
        if not jacobian:
            return result,phase,envelope
        phase_slope=envelope*(-sine*a+cosine*b)
        common_slope=(phase_slope*2*np.pi*self.orders).sum(axis=1)
        blocks=[envelope*cosine,envelope*sine,common_slope[:,None]*self.phase_basis,
            (partial[:,:,None]/envelope[:,:,None]*self.envelope_basis[:,None,:]).reshape(len(self.time),-1)]
        blocks.extend(phase_slope[:,index,None]*self.departure_basis for index in self.selected)
        return result,np.column_stack(blocks)

    def bounds(self,plan,variant):
        lower=np.full(self.parameter_count,-plan['amplitude_control_bound'])
        upper=-lower
        lower[:2*self.parts]=-1
        upper[:2*self.parts]=1
        start=2*self.parts
        lower[start:start+self.phase_count]=-plan['phase_control_bound_cycles']
        upper[start:start+self.phase_count]=plan['phase_control_bound_cycles']
        lower[self.base_count:]=-variant['departure_control_bound_radians']
        upper[self.base_count:]=variant['departure_control_bound_radians']
        return lower,upper
