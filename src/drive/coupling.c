#include "coupling.h"
#include <math.h>
#include <string.h>
static double factor(const VslCouplingInput *p,double torque) {
    return torque>=0?p->efficiency:1/p->efficiency;
}
static double evaluate(const VslCouplingInput *p,double torque,double *omega,double *speed) {
    *omega=fmax(0,p->omega_rad_s+p->dt*(p->engine_torque_nm-torque)/p->engine_inertia_kg_m2);
    *speed=fmax(0,p->speed_mps+p->dt*(torque*p->angular_per_metre*factor(p,torque)-p->road_force_n)/p->mass_kg);
    return *omega-p->angular_per_metre*(*speed);
}
int vsl_coupling_solve(const VslCouplingInput *p,VslCouplingResult *r) {
    double lo,hi,torque=0,slip,omega,speed,dw,dv,eta;unsigned i;
    if(!p||!r)return 0;
    memset(r,0,sizeof *r);
    if(!isfinite(p->omega_rad_s)||!isfinite(p->speed_mps)||!isfinite(p->engine_torque_nm)||
       !isfinite(p->road_force_n)||!isfinite(p->engine_inertia_kg_m2)||!isfinite(p->mass_kg)||
       !isfinite(p->angular_per_metre)||!isfinite(p->efficiency)||!isfinite(p->positive_capacity_nm)||
       !isfinite(p->negative_capacity_nm)||!isfinite(p->dt)||p->dt<=0||p->omega_rad_s<0||
       p->speed_mps<0||p->road_force_n<0||p->engine_inertia_kg_m2<=0||p->mass_kg<=0||
       p->angular_per_metre<0||p->efficiency<=0||p->efficiency>1||
       p->positive_capacity_nm<0||p->negative_capacity_nm<0)return 0;
    if(p->angular_per_metre>0) {
        lo=-p->negative_capacity_nm;hi=p->positive_capacity_nm;
        slip=evaluate(p,0,&omega,&speed);
        if(slip>0)lo=0;else if(slip<0)hi=0;
        if(slip!=0) {
            if(evaluate(p,lo,&omega,&speed)<0)torque=lo;
            else if(evaluate(p,hi,&omega,&speed)>0)torque=hi;
            else {
                /* Slip is monotone in clutch torque, including omega=0/v=0
                   active sets. Bisection avoids a guessed lock threshold or
                   a discontinuous explicit friction sign at zero slip. */
                for(i=0;i<44;++i) {
                    torque=.5*(lo+hi);
                    if(evaluate(p,torque,&omega,&speed)>0)lo=torque;else hi=torque;
                }
                torque=.5*(lo+hi);
            }
        }
    }
    r->slip_rad_s=evaluate(p,torque,&r->omega_rad_s,&r->speed_mps);
    r->clutch_torque_nm=torque;r->locked=p->angular_per_metre>0&&fabs(r->slip_rad_s)<1e-7;
    eta=factor(p,torque);dw=r->omega_rad_s-p->omega_rad_s;dv=r->speed_mps-p->speed_mps;
    r->energy_before_j=.5*p->engine_inertia_kg_m2*p->omega_rad_s*p->omega_rad_s+.5*p->mass_kg*p->speed_mps*p->speed_mps;
    r->energy_after_j=.5*p->engine_inertia_kg_m2*r->omega_rad_s*r->omega_rad_s+.5*p->mass_kg*r->speed_mps*r->speed_mps;
    r->engine_work_j=p->engine_torque_nm*r->omega_rad_s*p->dt;
    r->road_work_j=p->road_force_n*r->speed_mps*p->dt;
    r->clutch_heat_j=fmax(0,torque*r->slip_rad_s*p->dt);
    r->transmission_loss_j=torque*p->angular_per_metre*r->speed_mps*(1-eta)*p->dt;
    /* This separately reported term is backward-Euler numerical damping,
       not physical clutch heat. Work uses end-of-step velocities. */
    r->numerical_loss_j=.5*p->engine_inertia_kg_m2*dw*dw+.5*p->mass_kg*dv*dv;
    r->energy_error_j=r->energy_after_j-r->energy_before_j-r->engine_work_j+
        r->road_work_j+r->clutch_heat_j+r->transmission_loss_j+r->numerical_loss_j;
    return 1;
}
