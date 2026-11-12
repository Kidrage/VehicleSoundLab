#define _CRT_SECURE_NO_WARNINGS
#include "resonant_detail_io/profile.h"
#include "resonant_detail/voice.h"
#include "resonant_detail/envelope.h"
#include "residual_dense/voice.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line%d: %s\n",__LINE__,#x);return 1;}}while(0)
static RdtProfile model,saved;
static RdtVoice first,second,before;
static void fixture(void) {
    memset(&model,0,sizeof model);model.rate=48000;model.count=1;model.base_hz=40;
    model.band[0].low_hz=400;model.band[0].high_hz=6000;model.band[0].sigma=1;
    model.band[0].gain=.1;model.band[0].right_over_left=.8;model.band[0].order=2;
    model.band[0].a[0]=1;model.band[0].a[1]=-.97;model.band[0].a[2]=.97*.97;
    model.band[0].sections=1;model.band[0].sos[0][0]=model.band[0].sos[0][3]=1;
}
int main(int argc,char **argv) {
    unsigned i;double error=0,out[2],other[2],bands[RDT_MAX_BANDS];RdtFilter filter={0};FILE *file;
    CHECK(argc==3);
    /* Both public headers and implementations must coexist in one host. */
    CHECK(!rd_voice_init(NULL,NULL,NULL,71,1,1));
    fixture();CHECK(rdt_profile_valid(&model));
    for(i=0;i<256;++i) {
        double expected=pow(.97,(double)i)*sin((i+1)*3.14159265358979323846/3)/sin(3.14159265358979323846/3);
        double x=rdt_filter_source(&filter,model.band,i?0:1);
        if(fabs(x-expected)>error)error=fabs(x-expected);
    }
    CHECK(error<5e-14);
    model.band[0].envelope_order=1;model.band[0].beta[0]=.2;
    CHECK(fabs(rdt_envelope_amplitude(model.band,0)-sqrt(1.2))<1e-14);
    CHECK(fabs(rdt_envelope_amplitude(model.band,.25)-1)<1e-14);
    CHECK(fabs(rdt_envelope_amplitude(model.band,.5)-sqrt(.8))<1e-14);
    CHECK(rdt_profile_valid(&model));saved=model;
    model.band[0].beta[0]=2;CHECK(!rdt_profile_valid(&model));model=saved;
    model.band[0].a[2]=1.01;CHECK(!rdt_profile_valid(&model));model=saved;
    model.band[0].sos[0][5]=1.01;CHECK(!rdt_profile_valid(&model));model=saved;
    model.band[0].gain=NAN;CHECK(!rdt_profile_valid(&model));model=saved;
    CHECK(rdt_voice_init(&first,&model,71));CHECK(rdt_voice_init(&second,&model,71));
    for(i=0;i<8192;++i) {
        double phase=fmod(i*.00173,1);
        CHECK(rdt_voice_tick(&first,phase,out,bands));CHECK(rdt_voice_tick(&second,phase,other,NULL));
        CHECK(!memcmp(out,other,sizeof out));CHECK(isfinite(out[0]));
        CHECK(fabs(out[1]-.8*out[0])<1e-15);
    }
    CHECK(!memcmp(&first,&second,sizeof first));before=first;out[0]=12;out[1]=34;
    CHECK(!rdt_voice_tick(&first,NAN,out,NULL));CHECK(out[0]==12&&out[1]==34);
    CHECK(!rdt_voice_tick(&first,1,out,NULL));CHECK(!memcmp(&before,&first,sizeof first));
    model.band[0].a[2]=2;CHECK(!rdt_voice_init(&first,&model,71));CHECK(!memcmp(&before,&first,sizeof first));
    model=saved;
    file=tmpfile();CHECK(file!=NULL);fputs("VSL_RESONANT_DETAIL 1 48000 99 0 40\n",file);rewind(file);
    CHECK(!rdt_profile_read(file,&model));CHECK(!memcmp(&model,&saved,sizeof model));fclose(file);
    file=tmpfile();CHECK(file!=NULL);fputs("VSL_RESONANT_DETAIL 1 48000 1 0 40\n2 1 0 nan",file);rewind(file);
    CHECK(!rdt_profile_read(file,&model));CHECK(!memcmp(&model,&saved,sizeof model));fclose(file);
    for(i=1;i<3;++i){CHECK(rdt_profile_load(argv[i],&model));CHECK(rdt_voice_init(&first,&model,71));}
    puts("resonant detail: pole/envelope bounds, impulse, stereo, reset, phase rejection, transactional parsing pass");
    return 0;
}
