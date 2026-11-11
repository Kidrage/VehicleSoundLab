#include "core/engine.h"
#include "core/modules.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
static int failures;
#define CHECK(x,m) do { if(!(x)) { fprintf(stderr,"FAIL: %s\n",m);++failures; } } while(0)
typedef struct { double re,im; } Complex;
static Complex project(const double *x,int count,double frequency) {
    Complex z={0,0};int i;
    for(i=0;i<count;++i) { double angle=2*VSL_PI*frequency*i/48000.;z.re+=x[i]*cos(angle);z.im-=x[i]*sin(angle); }
    z.re*=2./count;z.im*=2./count;return z;
}
int main(void) {
    VslEngine *e=malloc(sizeof *e);int total=57600,warm=24000,i,r,j,side,n;
    double *samples[2]={malloc((size_t)total*sizeof(double)),malloc((size_t)total*sizeof(double))};
    double rpms[]={1200,2400,4000,6000,8000},loads[]={.18,.85};
    if(!e||!samples[0]||!samples[1])return 2;
    for(r=0;r<5;++r)for(j=0;j<2;++j) {
        double bank=rpms[r]/24.;
        vsl_init(e,48000,48271);e->smooth=vsl_default_params(VSL_V10);
        e->smooth.irregularity=0;e->control.rpm=rpms[r];e->control.load=loads[j];
        e->voice.dna_gain=.30+.64*loads[j];e->voice.high_gain=.08+.92*loads[j];
        e->voice.pull=loads[j];e->voice.cutoff_ratio=1;
        vsl_dna_update(e);vsl_high_orders_update(e);
        for(i=0;i<total+warm;++i) {
            VslObjectFrame o={0};double l,rr;
            e->control.phase=fmod(2*VSL_PI*rpms[r]/120*i/48000.,2*VSL_PI);
            vsl_dna_tick(e,&l,&rr);vsl_high_orders_tick(e,&o);
            if(i>=warm) {
                samples[0][i-warm]=l*e->smooth.dna*.65+o.sample[0];
                samples[1][i-warm]=rr*e->smooth.dna*.65+o.sample[1];
            }
        }
        for(side=0;side<2;++side) {
            Complex previous=project(samples[side],total,bank*25);
            double amplitude=hypot(previous.re,previous.im);
            for(n=26;n<=29;++n) {
                Complex now=project(samples[side],total,bank*n);
                double next=hypot(now.re,now.im),db=20*log10(next/amplitude);
                CHECK(isfinite(db)&&db>-6&&db<6,"actual emitted bank harmonics have no artificial boundary hole or jump");
                amplitude=next;
            }
        }
        for(n=25;n<=29;++n) {
            Complex l=project(samples[0],total,bank*n),rr=project(samples[1],total,bank*n);
            double phase=atan2(rr.im,rr.re)-atan2(l.im,l.re);
            double expected=-2*VSL_PI*(90./144)*n-2*VSL_PI*bank*n*vsl_profile(VSL_V10)->bank_delay;
            CHECK(fabs(atan2(sin(phase-expected),cos(phase-expected)))<.0001,"low/continued/high spectra retain the same emitted bank phase");
        }
    }
    free(e);free(samples[0]);free(samples[1]);
    if(!failures)puts("PASS: measured two-bank spectral continuity across five RPMs/two loads; phase retained");
    return failures?1:0;
}
