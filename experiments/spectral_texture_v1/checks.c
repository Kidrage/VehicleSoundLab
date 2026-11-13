#define _CRT_SECURE_NO_WARNINGS
#include "partitioned_fir/filter.h"
#include "spectral_texture/voice.h"
#include "spectral_texture/io.h"
#include "resonant_detail/excitation.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line%u: %s\n",(unsigned)__LINE__,#x);return 1;}}while(0)
#define PI 3.14159265358979323846
static SfProfile profile,before;
static int fft(void) {
    PfFft plan;PfComplex x[PF_FFT],original[PF_FFT];unsigned n,k;
    pf_fft_init(&plan);
    for(n=0;n<PF_FFT;++n){x[n].re=sin(.31*n)+.02*cos(.7*n);x[n].im=.03*sin(.59*n);}
    memcpy(original,x,sizeof x);pf_fft(&plan,x,0);
    for(k=0;k<PF_FFT;++k) {
        double re=0,im=0;
        for(n=0;n<PF_FFT;++n){double a=-2*PI*k*n/PF_FFT,c=cos(a),s=sin(a);re+=original[n].re*c-original[n].im*s;im+=original[n].re*s+original[n].im*c;}
        CHECK(fabs(x[k].re-re)<2e-10&&fabs(x[k].im-im)<2e-10);
    }
    pf_fft(&plan,x,1);
    for(n=0;n<PF_FFT;++n)CHECK(fabs(x[n].re-original[n].re)<1e-12&&fabs(x[n].im-original[n].im)<1e-12);
    return 0;
}
static int convolution(void) {
    double taps[513],input[2048],a[PF_BLOCK],b[PF_BLOCK],bad[PF_BLOCK]={0};unsigned n,j,start;
    PfKernel *kernel;PfState *one,*two;
    for(n=0;n<513;++n)taps[n]=.01*cos(.7*n)*exp(-(double)n/50.);taps[512]=.02;
    for(n=0;n<2048;++n)input[n]=.1*sin(.67*n);
    input[0]+=1;input[255]+=1;input[256]+=1;input[511]+=1;input[512]+=1;input[1023]+=1;
    kernel=pf_kernel_create(taps,513);CHECK(kernel);one=pf_state_create(kernel);two=pf_state_create(kernel);CHECK(one&&two);
    bad[7]=NAN;CHECK(!pf_filter_block(one,bad,a));
    CHECK(!pf_filter_block(one,input,NULL));
    for(start=0;start<2048;start+=PF_BLOCK) {
        memcpy(b,input+start,sizeof b);CHECK(pf_filter_block(one,input+start,a)&&pf_filter_block(two,b,b));
        CHECK(!memcmp(a,b,sizeof a));
        for(n=0;n<PF_BLOCK;++n) {
            double truth=0;for(j=0;j<513&&j<=start+n;++j)truth+=taps[j]*input[start+n-j];
            CHECK(fabs(a[n]-truth)<1e-12);
        }
    }
    pf_state_destroy(one);pf_state_destroy(two);pf_kernel_destroy(kernel);
    taps[0]=NAN;CHECK(!pf_kernel_create(taps,513));taps[0]=65;CHECK(!pf_kernel_create(taps,513));
    CHECK(!pf_kernel_create(taps,0)&&!pf_kernel_create(NULL,1));return 0;
}
static int source(void) {
    SfBank *bank;SfVoice *a,*b;RdtExcitation rng[2];double raw[2][3014],x[2],y[2],bands[SF_MAX_BANDS];unsigned n,i;
    memset(&profile,0,sizeof profile);profile.rate=48000;profile.count=2;profile.warmup_frames=13;
    for(i=0;i<2;++i) {
        SfBand *m=profile.band+i;m->count=2;m->taps[0]=.8;m->taps[1]=.6;
        m->gain=i?.03:.01;m->right_over_left=i?-.3:.7;
        rdt_excitation_init(rng+i,UINT64_C(149921)^(UINT64_C(0x9E3779B97F4A7C15)*(i+1)));
        for(n=0;n<3014;++n)raw[i][n]=rdt_excitation_next(rng+i);
    }
    CHECK(sf_profile_valid(&profile));bank=sf_bank_create(&profile);CHECK(bank);
    /* Bank owns compiled parameters; source-profile lifetime is over. */
    memset(&profile,0,sizeof profile);a=sf_voice_create(bank,149921);b=sf_voice_create(bank,149921);CHECK(a&&b);
    CHECK(!sf_voice_tick(a,NULL,NULL)&&!sf_voice_process(a,NULL,1));
    for(n=0;n<3001;++n) {
        double expected[2]={0,0};CHECK(sf_voice_tick(a,x,bands)&&sf_voice_process(b,y,1));
        CHECK(!memcmp(x,y,sizeof x));
        for(i=0;i<2;++i) {
            double value=(.8*raw[i][n+13]+.6*raw[i][n+12])*(i?.03:.01);
            CHECK(fabs(bands[i]-value)<1e-12);expected[0]+=value;expected[1]+=value*(i?-.3:.7);
        }
        CHECK(fabs(x[0]-expected[0])<1e-12&&fabs(x[1]-expected[1])<1e-12);
    }
    sf_voice_destroy(a);sf_voice_destroy(b);sf_bank_destroy(bank);return 0;
}
static int input(void) {
    const char *bad[]={"VSL_SPECTRAL_TEXTURE 1 48000 1 0 1 .1 .7 nan",
        "VSL_SPECTRAL_TEXTURE 1 48000 1.0 0 1 .1 .7 .2",
        "VSL_SPECTRAL_TEXTURE 1 48000 1 0 1 .1 .7 .2 extra",
        "VSL_SPECTRAL_TEXTURE 1 48000 1 0 2 .1 .7 .2",
        "VSL_SPECTRAL_TEXTURE 2 48000 1 0 1 .1 .7 .2"};
    FILE *f;unsigned i;memset(&profile,0,sizeof profile);before=profile;
    for(i=0;i<sizeof bad/sizeof *bad;++i) {
        f=tmpfile();CHECK(f);fputs(bad[i],f);rewind(f);
        CHECK(!sf_profile_read(f,&profile)&&!memcmp(&profile,&before,sizeof profile));CHECK(!fclose(f));
    }
    f=tmpfile();CHECK(f);fputs("VSL_SPECTRAL_TEXTURE 1 48000 1 13 2 .1 -.7 .8 .6\n",f);rewind(f);
    CHECK(sf_profile_read(f,&profile)&&profile.band[0].count==2&&profile.band[0].taps[1]==.6);CHECK(!fclose(f));return 0;
}
int main(void){CHECK(!fft());CHECK(!convolution());CHECK(!source());CHECK(!input());puts("spectral_texture_contracts_passed=1");return 0;}
