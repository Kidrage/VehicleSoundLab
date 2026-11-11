#include "core/engine.h"
#include "core/modules.h"
#include "profiles/combustion.h"
#include "profiles/firing.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
static int failures;
#define CHECK(x,m) do { if(!(x)) { fprintf(stderr,"FAIL: %s\n",m);++failures; } } while(0)
static void prepare(VslEngine *e,double rate,double rpm) {
    vsl_init(e,rate,48271);e->control.rpm=rpm;e->drive.combustion=1;e->drive.fuel.command=1;
    e->voice.dna_gain=e->voice.high_gain=1;e->smooth.irregularity=1;
}
static void clock_and_variation(VslEngine *e) { vsl_clocks_tick(e);vsl_combustion_tick(e); }
int main(void) {
    VslEngine *e=malloc(sizeof *e);int i,r;double rates[]={16000,48000,192000};
    if(!e)return 2;
    for(r=0;r<3;++r) {
        double min_gain=2,max_gain=0,previous_phase;unsigned counts[2];
        const VslCombustionProfile *p=vsl_combustion_profile(VSL_V10);
        prepare(e,rates[r],2400);
        for(i=0;i<(int)rates[r];++i) {
            double expected;previous_phase=e->control.phase;
            expected=fmod(previous_phase+2*VSL_PI*20/rates[r],2*VSL_PI);
            clock_and_variation(e);
            CHECK(e->control.phase==expected,"pressure timing cannot retime the drivetrain crank");
            min_gain=fmin(min_gain,e->combustion.gain[0]);max_gain=fmax(max_gain,e->combustion.gain[0]);
            CHECK(fabs(e->combustion.phase_delta[0])<=2*VSL_PI*20*p->idle_arrival_seconds,"pressure arrival phase stays within explicit engineering bound");
            CHECK(e->combustion.gain[0]>=1-p->idle_amplitude&&e->combustion.gain[0]<=1+p->idle_amplitude,"pressure amplitude remains positive and bounded");
        }
        CHECK(max_gain-min_gain>.05,"variation check exercises active nonzero modulation");
        CHECK(e->combustion.events[0]>=100&&e->combustion.events[0]<=101&&e->combustion.events[1]>=100&&e->combustion.events[1]<=101,"each bank has one new coefficient pair per firing interval");
        counts[0]=e->combustion.events[0];counts[1]=e->combustion.events[1];e->drive.fuel.command=0;
        for(i=0;i<(int)(rates[r]*.1);++i)clock_and_variation(e);
        CHECK(e->combustion.events[0]==counts[0]&&e->combustion.events[1]==counts[1],"fuel cut creates no new fired-pressure variation events");
        e->drive.fuel.command=1;for(i=0;i<(int)(rates[r]*.1);++i)clock_and_variation(e);
        CHECK(e->combustion.events[0]>counts[0]&&e->combustion.events[1]>counts[1],"refuel resumes pressure event variation");
    }
    /* A shared pressure phase/gain must affect low and high OSC paths equally.
       Force one overlapping bank harmonic, bypassing the normal crossover. */
    prepare(e,48000,2400);e->smooth.detail=e->smooth.dna=1;e->smooth.brightness=.5;
    { double angle=-2*VSL_PI*6*(vsl_bank_offset_cycles(VSL_V10)+100*vsl_profile(VSL_V10)->bank_delay);
      e->dna.real[29]=e->dna.target_real[29]=1;
      e->dna.right_real[29]=e->dna.target_right_real[29]=cos(angle);
      e->dna.right_imag[29]=e->dna.target_right_imag[29]=sin(angle);
      e->high_orders.active=6;e->high_orders.target[5]=e->high_orders.amplitude[5]=1;
      for(i=0;i<24000;++i) {
          VslObjectFrame o={0};double l,rr;
          clock_and_variation(e);vsl_dna_tick(e,&l,&rr);vsl_high_orders_tick(e,&o);
          CHECK(fabs(l-o.sample[0])<1e-12&&fabs(rr-o.sample[1])<1e-12,"low/high order oscillators share actual pressure phase and event amplitude");
      } }
    prepare(e,48000,2400);e->control.phase=(VSL_PI-1e-7)/5;vsl_combustion_tick(e);
    e->control.phase=(VSL_PI+1e-7)/5;vsl_combustion_tick(e);
    CHECK(fabs(e->combustion.gain[0]-1)<1e-12&&fabs(e->combustion.phase_delta[0])<1e-12,"new event coefficients enter at a zero-value and zero-slope modulation boundary");
    prepare(e,16000,10000);clock_and_variation(e);vsl_dna_update(e);vsl_high_orders_update(e);
    CHECK(e->combustion.stretch>1,"active pressure warp reserves sample-rate headroom");
    for(i=0;i<VSL_PARTIALS;++i)if((i+1)*10000./120*e->combustion.stretch>=.475*16000)
        CHECK(e->dna.target_real[i]==0&&e->dna.target_imag[i]==0,"low OSC coefficients respect conservative modulation margin");
    for(i=0;i<VSL_HIGH_ORDERS;++i)if((i+1)*10000.*10/240*e->combustion.stretch>=.46*16000)
        CHECK(e->high_orders.target[i]==0,"high OSC coefficients respect conservative modulation margin");
    prepare(e,48000,2400);clock_and_variation(e);e->target.combustion_variation=0;clock_and_variation(e);
    CHECK(e->combustion.mix>0&&e->combustion.mix<1,"runtime pressure-model bypass is smoothed");
    for(i=0;i<48000;++i)clock_and_variation(e);
    CHECK(e->combustion.mix==0&&e->combustion.gain[0]==1&&e->combustion.phase_delta[0]==0,"settled bypass reaches exact legacy pressure path");
    e->target.combustion_variation=1;e->dna.custom_count=1;clock_and_variation(e);
    CHECK(e->combustion.mix==0&&e->combustion.gain[0]==1&&e->combustion.stretch==1,"imported DNA cannot inherit factory pressure timing");
    e->dna.custom_count=0;e->smooth.pure_osc=1;clock_and_variation(e);
    CHECK(e->combustion.mix==0,"strict Pure OSC retains deterministic seed-independent policy");
    free(e);if(!failures)puts("PASS: bounded event variation, low/high pressure coherence, independent crank, cut/refuel, phase margin and explicit bypass policies");
    return failures?1:0;
}
