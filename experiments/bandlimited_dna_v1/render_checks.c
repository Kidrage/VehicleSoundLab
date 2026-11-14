#include "test_models.h"
#include "dna_atlas/voice.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
static SdProfile model,other;
static SaBank legacy,bounded;
static SaVoice a,b,muted;
static double whole[2*12000],parts[2*12000];
static double taper(double f) {
    double t;if(f<=19200)return 1;if(f>=21600)return 0;
    t=(f-19200)/2400;return 1-3*t*t+2*t*t*t;
}
static void tone(unsigned order) {
    bd_model(&model,90,288,0);memset(model.harmonic,0,sizeof model.harmonic);
    model.harmonic[order-1].mean[0]=.2*cos(.23);
    model.harmonic[order-1].mean[1]=.2*sin(.23);
    model.harmonic[order-1].mean[2]=.13*cos(-.71);
    model.harmonic[order-1].mean[3]=.13*sin(-.71);
}
int main(void) {
    const SdProfile *p[2]={&model,&other};
    const unsigned orders[]={1,213,214,220,239,240,267,288};
    unsigned i,n,at,chunk;double z[2],max_error=0,sweep_error=0,phase,root,expected;
    for(i=0;i<sizeof orders/sizeof orders[0];++i) {
        unsigned h=orders[i];tone(h);
        CHECK(sa_bank_init_bandlimited(&bounded,p,1,0));
        CHECK(sa_voice_init(&a,&bounded,23117,90,0,1));
        for(n=0;n<48000;++n) {
            phase=a.phase;sa_voice_tick(&a,z);
            expected=.2*taper(h*90.)*cos(h*phase+.23);
            max_error=fmax(max_error,fabs(z[0]-expected));
            max_error=fmax(max_error,fabs(z[1]-.13*taper(h*90.)*cos(h*phase-.71)));
            if(h>=240)CHECK(z[0]==0&&z[1]==0);
        }
    }
    CHECK(max_error<1e-9);
    /* One nonzero high order crosses both taper edges, then returns. Expected
       phase uses the pre-sample phase and the newly smoothed actual root. */
    tone(220);CHECK(sa_bank_init_bandlimited(&bounded,p,1,0));
    CHECK(sa_voice_init(&a,&bounded,23117,80,0,1));phase=0;root=80;
    for(n=0;n<30000;++n) {
        if(n==1000)CHECK(sa_voice_set(&a,105,0,1));
        if(n==15000)CHECK(sa_voice_set(&a,80,0,1));
        root+=a.follow*((n>=1000&&n<15000?105:80)-root);
        sa_voice_tick(&a,z);
        expected=.2*taper(220*root)*cos(220*phase+.23);
        sweep_error=fmax(sweep_error,fabs(z[0]-expected));
        sweep_error=fmax(sweep_error,fabs(z[1]-.13*taper(220*root)*cos(220*phase-.71)));
        phase+=2*BD_PI*root/48000;if(phase>=2*BD_PI)phase-=2*BD_PI;
        CHECK(a.phase==phase&&a.root_hz==root&&a.frame==n+1);
    }
    CHECK(sweep_error<1e-9);
    /* Same old-compatible bank/alignment and exact stochastic renderer state. */
    bd_model(&model,40,288,1);bd_model(&other,60,288,1);
    CHECK(sa_bank_init(&legacy,p,2,8)&&sa_bank_init_bandlimited(&bounded,p,2,8));
    CHECK(!memcmp(&legacy,&bounded,sizeof legacy));
    CHECK(sa_voice_init(&a,&legacy,61927,50,1,1)&&sa_voice_init(&b,&bounded,61927,50,1,1));
    sa_voice_process(&a,whole,12000);sa_voice_process(&b,parts,12000);
    CHECK(!memcmp(whole,parts,sizeof whole));b.bank=a.bank;CHECK(!memcmp(&a,&b,sizeof a));
    /* High-root textured bank, one call vs irregular blocks vs muted branch. */
    bd_model(&model,80,288,1);bd_model(&other,100,288,1);
    CHECK(sa_bank_init_bandlimited(&bounded,p,2,8));
    CHECK(sa_voice_init(&a,&bounded,61927,90,1,1)&&sa_voice_init(&b,&bounded,61927,90,1,1));
    CHECK(sa_voice_init(&muted,&bounded,61927,90,0,0));
    sa_voice_process(&a,whole,12000);
    for(at=0;at<12000;at+=chunk) {
        chunk=1+(at*17)%509;if(chunk>12000-at)chunk=12000-at;
        sa_voice_process(&b,parts+2*at,chunk);
        for(n=0;n<chunk;++n){sa_voice_tick(&muted,z);CHECK(z[0]==0&&z[1]==0);}
    }
    CHECK(!memcmp(whole,parts,sizeof whole)&&!memcmp(&a,&b,sizeof a));
    CHECK(!memcmp(a.texture,muted.texture,sizeof a.texture)&&a.phase==muted.phase);
    CHECK(a.texture[0].updates>0&&a.texture[1].updates==a.texture[0].updates);
    printf("PASS carrier suppression/stereo/continuous sweep/chunks/state; static %.12g sweep %.12g FS\n",max_error,sweep_error);
    return 0;
}
