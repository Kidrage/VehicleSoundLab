#include "core/engine.h"
#include "io/wav.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
static int failures;
#define CHECK(x,msg) do { if(!(x)) { fprintf(stderr,"FAIL: %s\n",msg); ++failures; } } while(0)
int main(void) {
    VslEngine*a=(VslEngine*)malloc(sizeof *a),*b=(VslEngine*)malloc(sizeof *b);
    float x[2048],y[2048]; int profile,block,i;
    CHECK(a&&b,"allocate engine"); if(!a||!b)return 2;
    for(profile=0;profile<VSL_PROFILE_COUNT;++profile) {
        VslParams p=vsl_default_params(profile); p.rpm=8400; p.load=1;
        vsl_init(a,48000,48271); vsl_init(b,48000,48271); vsl_set_params(a,&p); vsl_set_params(b,&p);
        for(block=0;block<80;++block) {
            vsl_process(a,x,1024);
            for(i=0;i<4;++i)vsl_process(b,y+i*512,256);
            CHECK(!memcmp(x,y,sizeof x),"deterministic and independent of host block size");
            for(i=0;i<2048;++i)CHECK(isfinite(x[i])&&fabs(x[i])<=.95001,"finite protected output");
        }
        CHECK(a->peak>.001,"every profile actually starts and produces sound");
    }
    {
        VslParams p=vsl_default_params(0); p.pure_osc=1; p.rpm=6000; p.space=0;
        vsl_init(a,48000,1); vsl_init(b,48000,999); vsl_set_params(a,&p); vsl_set_params(b,&p);
        for(block=0;block<80;++block) { vsl_process(a,x,1024); vsl_process(b,y,1024); }
        CHECK(!memcmp(x,y,sizeof x),"settled pure OSC independent of stochastic seed");
        CHECK(a->peak>.001,"oscillator actually produces audio");
    }
    {
        VslParams p=vsl_default_params(0); p.rpm=NAN; p.master=NAN; p.load=INFINITY;
        vsl_set_params(a,&p); vsl_process(a,x,1024);
        for(i=0;i<2048;++i)CHECK(isfinite(x[i]),"invalid controls sanitized");
    }
    CHECK(!vsl_load_dna(a,"missing.dna"),"missing custom DNA fails explicitly");
    CHECK(!vsl_set_ir(a,x,1024,44100),"IR sample-rate mismatch rejected");
    for(profile=0;profile<3;++profile) {
        double sr=profile==0?32000:(profile==1?96000:192000); VslParams p=vsl_default_params(0);
        p.rpm=10000; p.load=1; p.pure_osc=1;
        vsl_init(a,sr,48271); vsl_set_params(a,&p);
        for(block=0;block<(int)(sr*2.5/1024);++block)vsl_process(a,x,1024);
        CHECK(a->control.rpm>9900,"bandlimit test reaches requested high RPM after startup");
        for(i=0;i<VSL_PARTIALS;++i)if((i+1)*a->control.rpm/120>=sr*.475)
            CHECK(a->dna.target_real[i]==0&&a->dna.target_imag[i]==0,"out-of-band partials removed");
    }
    free(a); free(b);
    if(!failures)puts("PASS: deterministic render, host block independence, output bounds, strict OSC, rate guards");
    return failures?1:0;
}
