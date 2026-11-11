#include "dna_atlas/voice.h"
#include "sound_dna/voice.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define PI 3.14159265358979323846
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"atlas check line%d: %s\n",__LINE__,#x);return 1; } } while(0)
static SaBank bank,saved;
static SdProfile a,b;
static SaVoice one,two,other;
static SdVoice legacy;
static double output[2048],fragmented[2048];

static void fixture(SdProfile *m,double hz,unsigned harmonics) {
    unsigned h;
    memset(m,0,sizeof *m);m->rate=48000;m->window=1024;m->hop=256;m->base_hz=hz;m->harmonics=harmonics;
    m->components=1;m->rho[0]=.6;
    for (h=0;h<harmonics;++h) {
        SdHarmonic *z=&m->harmonic[h];
        double phase=.3*h,amp=.12/(h+1);
        z->mean[0]=amp*cos(phase);z->mean[1]=amp*sin(phase);
        z->mean[2]=.7*amp*cos(phase+.4);z->mean[3]=.7*amp*sin(phase+.4);
        z->basis[0][0]=.001;z->basis[0][3]=.0007;z->rho=.3;
        z->root[0][0]=.0003;z->root[2][2]=.0002;
    }
}
int main(void) {
    const SdProfile *models[2]={&a,&b};
    unsigned n,h,c;
    double max_error=0,z[2],l[2],r[2];
    fixture(&a,40,8);b=a;b.base_hz=80;
    CHECK(sa_bank_init(&bank,models,2,0));
    CHECK(isfinite(sa_bank_sine(&bank,-1e-300))&&fabs(sa_bank_sine(&bank,-1e-300))<1e-12);
    for (n=0;n<10000;++n) {
        double angle=-20+40*n/9999.;
        CHECK(fabs(sa_bank_sine(&bank,angle)-sin(angle))<3e-7);
    }
    CHECK(sa_voice_init(&one,&bank,48271,60,1,1));
    CHECK(sd_voice_init(&legacy,&a,48271,1,1,1));
    /* Single anchor exactly follows the established fixed-phase voice. */
    CHECK(sa_bank_init(&saved,models,1,0));
    CHECK(sa_voice_init(&two,&saved,48271,40,1,1));
    for (n=0;n<10000;++n) {
        sa_voice_tick(&two,l);sd_voice_process(&legacy,r,1);
        for (c=0;c<2;++c) max_error=fmax(max_error,fabs(l[c]-r[c]));
    }
    CHECK(max_error<2e-10);
    /* Identical spectral models, different root labels: no crossfade beating,
       no magnitude dip; shared texture stream reproduces one retuned voice. */
    CHECK(sa_voice_init(&two,&saved,48271,60,1,1));
    for (n=0;n<20000;++n) {
        sa_voice_tick(&one,l);sa_voice_tick(&two,r);
        CHECK(fabs(l[0]-r[0])<2e-7&&fabs(l[1]-r[1])<2e-7);
    }
    CHECK(one.coverage==0&&one.lower==0&&one.upper==1&&fabs(one.blend-.5)<1e-12);
    CHECK(one.texture[0].rng==one.texture[1].rng);
    CHECK(sa_voice_init(&other,&bank,1,40-1e-10,0,1));sa_voice_tick(&other,z);CHECK(other.coverage==0);
    CHECK(sa_voice_init(&other,&bank,1,80+1e-10,0,1));sa_voice_tick(&other,z);CHECK(other.coverage==0);

    /* A known common cycle shift is removed with one offset for both channels. */
    for (h=0;h<b.harmonics;++h) for (c=0;c<2;++c) {
        double re=a.harmonic[h].mean[2*c],im=a.harmonic[h].mean[2*c+1],p=(h+1)*.7;
        b.harmonic[h].mean[2*c]=re*cos(p)-im*sin(p);
        b.harmonic[h].mean[2*c+1]=re*sin(p)+im*cos(p);
    }
    CHECK(sa_bank_init(&bank,models,2,8));
    CHECK(fabs(bank.offset[1]+.7)<1e-6);
    for (h=0;h<8;++h) CHECK(fabs(remainder((bank.phase[1][h][1]-bank.phase[1][h][0])-.4,2*PI))<1e-10);
    /* Genuine phase/timbre change at constant magnitude must survive the
       midpoint; complex-coefficient averaging would nearly cancel this case. */
    fixture(&a,40,1);b=a;b.base_hz=80;
    for (c=0;c<2;++c) {
        double re=a.harmonic[0].mean[2*c],im=a.harmonic[0].mean[2*c+1],p=PI-.2;
        b.harmonic[0].mean[2*c]=re*cos(p)-im*sin(p);
        b.harmonic[0].mean[2*c+1]=re*sin(p)+im*cos(p);
    }
    CHECK(sa_bank_init(&bank,models,2,0));
    CHECK(sa_voice_init(&one,&bank,1,60,0,1));
    sa_voice_tick(&one,z);
    CHECK(fabs(z[0]-.12*cos((PI-.2)/2))<1e-7);
    CHECK(fabs(z[1]-.084*cos(.4+(PI-.2)/2))<1e-7);
    for (n=0;n<1000;++n) {
        double phase=one.phase;sa_voice_tick(&one,z);
        CHECK(fabs(z[0]-.12*cos(phase+(PI-.2)/2))<2e-7);
        CHECK(fabs(z[1]-.084*cos(phase+.4+(PI-.2)/2))<2e-7);
    }
    /* Per-harmonic anti-alias suppression and smooth transition region. */
    fixture(&a,40,32);memset(a.harmonic,0,sizeof a.harmonic);
    a.harmonic[19].mean[0]=1;a.harmonic[29].mean[0]=1;
    CHECK(sa_bank_init(&bank,models,1,0));
    CHECK(sa_voice_init(&one,&bank,1,1000,0,1));
    for (n=0;n<2000;++n) {
        double phase=one.phase, x=1.0/3, taper=1-x*x*(3-2*x);
        sa_voice_tick(&one,z);CHECK(fabs(z[0]-taper*cos(20*phase))<1e-10&&z[1]==0);
    }
    CHECK(one.coverage==1&&fabs(one.root_hz-1000)<1e-12);

    /* Chunking and a muted alternate path must not alter RNG/clocks. */
    fixture(&a,40,8);b=a;b.base_hz=80;
    CHECK(sa_bank_init(&bank,models,2,8));
    CHECK(sa_voice_init(&one,&bank,999,20,1,1));
    CHECK(sa_voice_init(&two,&bank,999,20,1,1));
    CHECK(sa_voice_init(&other,&bank,999,20,0,0));
    sa_voice_process(&one,output,1024);
    for (n=0;n<1024;++n) { sa_voice_process(&two,fragmented+2*n,1);sa_voice_tick(&other,z); }
    CHECK(!memcmp(output,fragmented,sizeof output));
    CHECK(one.coverage==-1&&one.texture[1].updates>0&&one.phase==other.phase);
    CHECK(!memcmp(one.texture,other.texture,sizeof one.texture));
    saved=bank;
    CHECK(!sa_bank_init(&bank,models,0,0)&&!memcmp(&saved,&bank,sizeof bank));
    CHECK(!sa_voice_set(&one,NAN,1,1)&&one.root_target==20);
    CHECK(!sa_voice_set(&one,1001,1,1)&&!sa_voice_set(&one,60,1.1,1));
    printf("atlas analytic/morph/stereo/clock/alias checks passed; legacy max error %.12g\n",max_error);
    return 0;
}
