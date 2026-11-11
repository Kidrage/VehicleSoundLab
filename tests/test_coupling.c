#include "drive/coupling.h"
#include "core/engine.h"
#include <math.h>
#include <stdio.h>
#include <stdint.h>
static int failures;static uint32_t rng=48271;
#define CHECK(x,m) do { if(!(x)) { if(failures<12)fprintf(stderr,"FAIL: %s\n",m);++failures; } } while(0)
static double random01(void) { rng=rng*1664525u+1013904223u;return (rng>>8)*(1.0/16777216); }
static VslCouplingInput input(void) {
    VslCouplingInput p={0};p.omega_rad_s=300;p.speed_mps=20;
    p.engine_inertia_kg_m2=.22;p.mass_kg=1670;p.angular_per_metre=15;
    p.efficiency=.9;p.positive_capacity_nm=p.negative_capacity_nm=900;p.dt=.005;return p;
}
int main(void) {
    VslCouplingInput p=input();VslCouplingResult r;double expected,energy;int i;
    p.efficiency=1;p.engine_torque_nm=400;
    CHECK(vsl_coupling_solve(&p,&r),"valid two-inertia input");
    expected=p.engine_torque_nm*p.angular_per_metre/(p.mass_kg+p.engine_inertia_kg_m2*p.angular_per_metre*p.angular_per_metre);
    CHECK(fabs((r.speed_mps-p.speed_mps)/p.dt-expected)<1e-8,"locked acceleration matches analytic combined-inertia result");
    CHECK(r.locked&&fabs(r.omega_rad_s-r.speed_mps*p.angular_per_metre)<1e-7,"lock is solved rather than following a target RPM");
    CHECK(r.clutch_heat_j<1e-8&&fabs(r.energy_error_j)<1e-7,"static friction creates no heat and satisfies discrete energy balance");
    p=input();p.omega_rad_s=600;p.speed_mps=0;p.positive_capacity_nm=50;p.negative_capacity_nm=50;
    CHECK(vsl_coupling_solve(&p,&r)&&!r.locked&&r.clutch_heat_j>0,"slipping clutch converts relative kinetic energy to heat");
    CHECK(r.speed_mps>0&&r.omega_rad_s<p.omega_rad_s&&r.energy_after_j<r.energy_before_j,"coasting engine inertia may accelerate wheels while total energy decreases");
    p=input();p.positive_capacity_nm=p.negative_capacity_nm=0;p.engine_torque_nm=100;
    CHECK(vsl_coupling_solve(&p,&r)&&r.clutch_torque_nm==0&&r.speed_mps==p.speed_mps,"open clutch has zero wheel reaction");
    CHECK(fabs(r.omega_rad_s-p.omega_rad_s-p.dt*100/p.engine_inertia_kg_m2)<1e-10,"free engine integrates torque/inertia without a prescribed RPM curve");
    p=input();p.angular_per_metre=0;p.road_force_n=200;
    CHECK(vsl_coupling_solve(&p,&r)&&r.clutch_torque_nm==0&&r.speed_mps<p.speed_mps,"neutral is uncoupled even if capacity is supplied");
    p=input();p.omega_rad_s=0;p.speed_mps=0;p.engine_torque_nm=-70;p.road_force_n=20000;
    CHECK(vsl_coupling_solve(&p,&r)&&r.omega_rad_s==0&&r.speed_mps==0&&fabs(r.energy_error_j)<1e-9,"unilateral rest constraints do not reverse either inertia");
    for(i=0;i<12000;++i) {
        p=input();p.omega_rad_s=1000*random01();p.speed_mps=100*random01();
        p.angular_per_metre=i%31==0?0:45*random01();p.efficiency=.55+.45*random01();
        p.positive_capacity_nm=1200*random01();p.negative_capacity_nm=1200*random01();
        p.engine_torque_nm=-150+800*random01();p.road_force_n=20000*random01();
        p.dt=.0005+.025*random01();p.engine_inertia_kg_m2=.1+.4*random01();
        p.mass_kg=800+1800*random01();
        CHECK(vsl_coupling_solve(&p,&r),"random physical input accepted");
        CHECK(r.clutch_torque_nm>=-p.negative_capacity_nm-1e-9&&r.clutch_torque_nm<=p.positive_capacity_nm+1e-9,"friction respects both directional capacity bounds");
        CHECK(r.clutch_torque_nm*r.slip_rad_s>=-1e-7,"friction always opposes end-of-step slip");
        CHECK(r.transmission_loss_j>=-1e-8&&r.clutch_heat_j>=0&&r.numerical_loss_j>=0,"physical and numerical dissipation are separately nonnegative");
        CHECK(fabs(r.energy_error_j)<2e-6,"engine/road work and all losses close the discrete energy balance");
        if(p.engine_torque_nm<=0)CHECK(r.energy_after_j<=r.energy_before_j+1e-6,"unpowered two-inertia system cannot create kinetic energy");
    }
    p=input();p.engine_torque_nm=0;energy=.5*p.engine_inertia_kg_m2*p.omega_rad_s*p.omega_rad_s+.5*p.mass_kg*p.speed_mps*p.speed_mps;
    p.angular_per_metre=33;
    CHECK(vsl_coupling_solve(&p,&r)&&fabs(r.energy_before_j-energy)<1e-8,"changing a gear does not change either physical inertia's stored energy");
    p=input();p.mass_kg=0;CHECK(!vsl_coupling_solve(&p,&r),"invalid inertia is rejected");
    if(!failures)puts("PASS: analytic coupling, slip/lock/rest, neutral, gear energy and 12000 discrete energy/passivity controls");
    return failures?1:0;
}
