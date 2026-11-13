#define _CRT_SECURE_NO_WARNINGS
#include "models.h"
#include "modal_source/io.h"
#include "modal_source/voice.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define PI 3.14159265358979323846
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line%d: %s\n",__LINE__,#x);return 1;}}while(0)
static MsProfile known(void) {
    MsProfile p;memset(&p,0,sizeof p);p.rate=48000;p.count=2;
    p.mode[0]=(MsMode){75.31,{.2,.12},{.31,-.4}};
    p.mode[1]=(MsMode){191.47,{.08,.06},{1.1,.7}};return p;
}
static int check_oracle(void) {
    MsProfile p=known();MsVoice v;unsigned n,c,k;double maximum=0;
    CHECK(ms_voice_init(&v,&p,1,1));
    for(n=0;n<48000*60u;++n) {
        double out[2];CHECK(ms_voice_tick(&v,out));
        CHECK(isfinite(out[0])&&isfinite(out[1]));
        if(n<24000||n%997==0)for(c=0;c<2;++c) {
            double want=0,error;
            for(k=0;k<p.count;++k)want+=p.mode[k].amplitude[c]*cos(2*PI*p.mode[k].hz*n/48000+p.mode[k].phase[c]);
            error=fabs(out[c]-want);if(error>maximum)maximum=error;CHECK(error<2e-8);
        }
    }
    /* A distinct inharmonic profile proves the kernel has no V10 constant. */
    p.mode[0].hz=113.17;p.mode[1].hz=289.3;CHECK(ms_voice_init(&v,&p,.9,.4));
    for(n=0;n<24000;++n) {
        double out[2];CHECK(ms_voice_tick(&v,out));
        for(c=0;c<2;++c) {
            double want=0;
            for(k=0;k<p.count;++k)want+=.4*p.mode[k].amplitude[c]*cos(2*PI*p.mode[k].hz*.9*n/48000+p.mode[k].phase[c]);
            CHECK(fabs(want-out[c])<1e-10);
        }
    }
    printf("60s_direct_cosine_max_FS_error=%.17g\n",maximum);return 0;
}
static int check_controls(void) {
    MsProfile p=known();MsVoice v;unsigned n,c,k,progress=0;double phase[2]={0,0},start_r=1,target_r=1,start_g=1,target_g=1;
    CHECK(ms_voice_init(&v,&p,1,1));
    for(n=0;n<5000;++n) {
        double out[2],r,g;
        if(n==0||n==1200||n==1500) {
            start_r=v.ratio.value;start_g=v.gain.value;
            target_r=n==0?.9:n==1200?1.1:1;target_g=n==0?.4:n==1200?.8:.2;progress=0;
            CHECK(ms_voice_set(&v,target_r,target_g));
        }
        /* Repeated240-frame input adoption must not postpone the endpoint. */
        if(n%240==0)CHECK(ms_voice_set(&v,target_r,target_g));
        if(progress<MS_RAMP_FRAMES)++progress;
        r=start_r+(target_r-start_r)*progress/MS_RAMP_FRAMES;
        g=start_g+(target_g-start_g)*progress/MS_RAMP_FRAMES;
        CHECK(ms_voice_tick(&v,out));
        CHECK(fabs(v.ratio.value-r)<1e-12&&fabs(v.gain.value-g)<1e-12);
        for(c=0;c<2;++c) {
            double want=0;
            for(k=0;k<p.count;++k)want+=g*p.mode[k].amplitude[c]*cos(phase[k]+p.mode[k].phase[c]);
            CHECK(fabs(want-out[c])<2e-9);
        }
        for(k=0;k<p.count;++k)phase[k]+=2*PI*p.mode[k].hz*r/48000;
        if(progress==MS_RAMP_FRAMES)CHECK(v.ratio.value==target_r&&v.gain.value==target_g);
    }
    return 0;
}
static int check_chunks_and_mute(void) {
    MsProfile p=known();MsVoice a,b,m;double left[1024],right[1024];unsigned i;
    CHECK(ms_voice_init(&a,&p,1,1));CHECK(ms_voice_init(&b,&p,1,1));CHECK(ms_voice_init(&m,&p,1,0));
    CHECK(ms_voice_process(&a,left,512));
    for(i=0;i<512;++i){double zero[2];CHECK(ms_voice_tick(&b,right+2*i));CHECK(ms_voice_tick(&m,zero));CHECK(zero[0]==0&&zero[1]==0);}
    CHECK(!memcmp(left,right,sizeof left)&&!memcmp(&a,&b,sizeof a));
    CHECK(!memcmp(m.cosine,a.cosine,sizeof a.cosine)&&!memcmp(m.sine,a.sine,sizeof a.sine));
    CHECK(ms_voice_process(&a,NULL,0));return 0;
}
static int check_limits(void) {
    MsProfile p=known(),bad;MsVoice v,before;unsigned k,n;double out[2]={17,19};
    CHECK(ms_voice_init(&v,&p,1,1));before=v;
    CHECK(!ms_voice_set(&v,NAN,1)&&!ms_voice_set(&v,0,1)&&!ms_voice_set(&v,1,INFINITY));
    CHECK(!ms_voice_tick(&v,NULL)&&!ms_voice_process(&v,NULL,1)&&!memcmp(&before,&v,sizeof v));
    bad=p;bad.mode[1].hz=bad.mode[0].hz;CHECK(!ms_voice_init(&v,&bad,1,1)&&!memcmp(&before,&v,sizeof v));
    bad=p;bad.mode[0].phase[0]=NAN;CHECK(!ms_profile_valid(&bad));
    bad=p;bad.mode[0].amplitude[0]=-1;CHECK(!ms_profile_valid(&bad));
    CHECK(!ms_voice_tick(NULL,out)&&out[0]==17&&out[1]==19);
    memset(&p,0,sizeof p);p.rate=48000;p.count=1;p.mode[0]=(MsMode){20000,{.2,.1},{.2,.4}};
    CHECK(ms_voice_init(&v,&p,4,1));for(n=0;n<8192;++n){CHECK(ms_voice_tick(&v,out));CHECK(out[0]==0&&out[1]==0);}
    CHECK(v.frame==8192&&v.sine[0]!=0);
    CHECK(ms_voice_init(&v,&p,1,1));
    for(n=0;n<2048;++n) {
        double u=800./2400,weight=1-u*u*(3-2*u);unsigned c;
        CHECK(ms_voice_tick(&v,out));
        for(c=0;c<2;++c)CHECK(fabs(out[c]-weight*p.mode[0].amplitude[c]*cos(2*PI*20000*n/48000+p.mode[0].phase[c]))<1e-11);
    }
    p.mode[0].amplitude[0]=p.mode[0].amplitude[1]=0;
    CHECK(ms_voice_init(&v,&p,1,1));for(n=0;n<2048;++n){CHECK(ms_voice_tick(&v,out));CHECK(out[0]==0&&out[1]==0);}
    p.count=MS_MAX_MODES;
    for(k=0;k<p.count;++k)p.mode[k]=(MsMode){100+73.17*k,{.001,.002},{.1*k,-.2*k}};
    CHECK(ms_voice_init(&v,&p,1,1));
    for(n=0;n<2048;++n) {
        unsigned c;CHECK(ms_voice_tick(&v,out));
        for(c=0;c<2;++c) {
            double want=0;
            for(k=0;k<p.count;++k)want+=p.mode[k].amplitude[c]*cos(2*PI*p.mode[k].hz*n/48000+p.mode[k].phase[c]);
            CHECK(fabs(want-out[c])<1e-11);
        }
    }
    return 0;
}
static int check_io(void) {
    const char *invalid[]={"VSL_MODAL_SOURCE 1 48000 65\n","VSL_MODAL_SOURCE 1 48000 1\n75 .2 .1 0\n",
        "VSL_MODAL_SOURCE 1 48000 1\n75 .2 .1 0 0\njunk","VSL_MODAL_SOURCE 1 48000 1\n75 nan .1 0 0\n",
        "VSL_MODAL_SOURCE -4294967295 48000 1\n75 .2 .1 0 0\n",
        "VSL_MODAL_SOURCE 1 48000 4294967297\n75 .2 .1 0 0\n"};
    MsProfile p=known(),before=p;unsigned i;FILE *f;
    for(i=0;i<sizeof invalid/sizeof invalid[0];++i){f=tmpfile();CHECK(f);fputs(invalid[i],f);rewind(f);CHECK(!ms_profile_read(f,&p)&&!memcmp(&p,&before,sizeof p));fclose(f);}
    f=tmpfile();CHECK(f);fputs("VSL_MODAL_SOURCE 1 48000 1\n75 .2 .1 .3 -.4\n",f);rewind(f);
    CHECK(ms_profile_read(f,&p)&&p.count==1&&p.mode[0].hz==75&&p.mode[0].phase[1]==-.4);fclose(f);return 0;
}
int main(int argc,char **argv) {
    CHECK(!check_oracle());CHECK(!check_controls());CHECK(!check_chunks_and_mute());CHECK(!check_limits());CHECK(!check_io());
    if(argc==3) {
        MiModels m,before;CHECK(mi_models_load(&m,argv[1],argv[2]));before=m;
        m.detail.band[0].envelope_order=1;m.detail.band[0].beta[0]=.01;CHECK(!mi_models_valid(&m));
        m=before;CHECK(!mi_models_load(&m,"missing-modal-file",argv[2])&&!memcmp(&m,&before,sizeof m));
    }else CHECK(argc==1);
    puts("modal_source_contracts_passed=1");return 0;
}
