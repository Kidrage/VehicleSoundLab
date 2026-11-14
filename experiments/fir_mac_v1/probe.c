#define _CRT_SECURE_NO_WARNINGS
#include "partitioned_fir/filter.h"
#include "mac.h"
#include "spectral_texture/io.h"
#include "resonant_detail/excitation.h"
#include <float.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#endif
#ifdef PF_HAVE_REFERENCE
PfKernel *reference_pf_kernel_create(const double *,unsigned);
void reference_pf_kernel_destroy(PfKernel *);
PfState *reference_pf_state_create(const PfKernel *);
void reference_pf_state_destroy(PfState *);
int reference_pf_filter_block(PfState *,const double *,double *);
#endif
#define CHECK(x) do{if(!(x)){fprintf(stderr,"FIR check line%u: %s\n",(unsigned)__LINE__,#x);return 0;}}while(0)
static uint64_t random_state=UINT64_C(761824351);
static double number(void) {
    uint64_t x=random_state;x^=x>>12;x^=x<<25;x^=x>>27;random_state=x;
    return ((double)((x*UINT64_C(2685821657736338717))>>11)/9007199254740992.)*2-1;
}
static void scalar(PfComplex *sum,const PfComplex *x,const PfComplex *h) {
    unsigned n;for(n=0;n<PF_FFT;++n){
        double re=x[n].re*h[n].re-x[n].im*h[n].im;
        double im=x[n].re*h[n].im+x[n].im*h[n].re;
        sum[n].re=sum[n].re+re;sum[n].im=sum[n].im+im;
    }
}
static int complex_cases(void) {
    PfComplex x[PF_FFT],h[PF_FFT],a[PF_FFT],b[PF_FFT];unsigned kind,p,n;
    CHECK(sizeof(PfComplex)==2*sizeof(double));
    for(kind=0;kind<5;++kind){
        for(n=0;n<PF_FFT;++n){a[n].re=number();a[n].im=number();}
        if(kind==1)memset(a,0,sizeof a);memcpy(b,a,sizeof a);
        for(p=0;p<32;++p){
            for(n=0;n<PF_FFT;++n){
                x[n]=(PfComplex){number(),number()};h[n]=(PfComplex){number(),number()};
                if(kind==1){x[n].re=(n&1)?-0.:0.;h[n].im=(n&2)?-0.:0.;}
                if(kind==2){x[n].re*=1e-300;x[n].im*=1e-300;h[n].re*=1e100;h[n].im*=1e100;}
                if(kind==3){x[n].re*=1e100;x[n].im*=1e100;h[n].re*=1e100;h[n].im*=1e100;}
                if(kind==4){x[n].re*=DBL_MIN;x[n].im*=DBL_MIN;}
            }
            scalar(a,x,h);pf_mac_add(b,x,h);CHECK(!memcmp(a,b,sizeof a));
        }
    }
    return 1;
}
static int filters(void) {
    const unsigned lengths[]={1,255,256,257,513,8191,8192};unsigned which;
    for(which=0;which<sizeof lengths/sizeof *lengths;++which){
        unsigned length=lengths[which],parts=(length+255)/256,frames=(3*parts+5)*256,n,j,at;
        double *taps=malloc(length*sizeof *taps),*input=malloc(frames*sizeof *input),a[PF_BLOCK],b[PF_BLOCK],bad[PF_BLOCK]={0};
        PfKernel *kernel;PfState *one,*two;
#ifdef PF_HAVE_REFERENCE
        PfKernel *old_kernel;PfState *old;double original[PF_BLOCK];
#endif
        CHECK(taps&&input);
        for(n=0;n<length;++n)taps[n]=.01*number()*exp(-(double)n/2000.);
        taps[0]=.7;taps[length-1]+=.25;
        for(n=0;n<frames;++n)input[n]=number();
        input[0]+=1;input[255]+=1;input[256]-=1;
        kernel=pf_kernel_create(taps,length);CHECK(kernel);one=pf_state_create(kernel);two=pf_state_create(kernel);CHECK(one&&two);
#ifdef PF_HAVE_REFERENCE
        old_kernel=reference_pf_kernel_create(taps,length);old=reference_pf_state_create(old_kernel);CHECK(old_kernel&&old);
#endif
        bad[PF_BLOCK-1]=NAN;CHECK(!pf_filter_block(one,bad,a));bad[PF_BLOCK-1]=1.01e100;CHECK(!pf_filter_block(one,bad,a));
        CHECK(!pf_filter_block(one,input,NULL));
        for(at=0;at<frames;at+=PF_BLOCK){
            memcpy(b,input+at,sizeof b);CHECK(pf_filter_block(one,input+at,a)&&pf_filter_block(two,b,b));CHECK(!memcmp(a,b,sizeof a));
#ifdef PF_HAVE_REFERENCE
            CHECK(reference_pf_filter_block(old,input+at,original));CHECK(!memcmp(a,original,sizeof a));
#endif
            for(n=0;n<PF_BLOCK;n+=255){double truth=0;
                for(j=0;j<length&&j<=at+n;++j)truth+=taps[j]*input[at+n-j];
                CHECK(fabs(a[n]-truth)<2e-12);
            }
        }
        pf_state_destroy(one);pf_state_destroy(two);pf_kernel_destroy(kernel);
#ifdef PF_HAVE_REFERENCE
        reference_pf_state_destroy(old);reference_pf_kernel_destroy(old_kernel);
#endif
        free(taps);free(input);
    }
    return 1;
}
#if defined(PF_HAVE_REFERENCE) && defined(_WIN32)
static SfProfile profile;
static double now(void){LARGE_INTEGER n,f;QueryPerformanceCounter(&n);QueryPerformanceFrequency(&f);return (double)n.QuadPart/f.QuadPart;}
static double cycle(void){ULONG64 n=0;QueryThreadCycleTime(GetCurrentThread(),&n);return (double)n;}
static int benchmark(const char *file,const char *trace) {
    enum {REPEATS=5,BLOCKS=1200,WARM=192};
    double *input=NULL,old_output[SF_MAX_BANDS][PF_BLOCK],new_output[SF_MAX_BANDS][PF_BLOCK];
    PfKernel *old_kernel[SF_MAX_BANDS]={0},*kernel[SF_MAX_BANDS]={0};
    PfState *old[SF_MAX_BANDS]={0},*state[SF_MAX_BANDS]={0};
    double total[2]={0},cycles[2]={0},maximum[2]={0};unsigned repeat,b,n,at,side;
    FILE *csv;CHECK(sf_profile_load(file,&profile)&&profile.count==6);
    input=malloc((size_t)profile.count*(BLOCKS+WARM)*PF_BLOCK*sizeof *input);CHECK(input);
    for(b=0;b<profile.count;++b){RdtExcitation rng;
        rdt_excitation_init(&rng,UINT64_C(149921)^(UINT64_C(0x9E3779B97F4A7C15)*(b+1)));
        for(n=0;n<(BLOCKS+WARM)*PF_BLOCK;++n)input[(size_t)b*(BLOCKS+WARM)*PF_BLOCK+n]=rdt_excitation_next(&rng);
        kernel[b]=pf_kernel_create(profile.band[b].taps,profile.band[b].count);
        old_kernel[b]=reference_pf_kernel_create(profile.band[b].taps,profile.band[b].count);CHECK(kernel[b]&&old_kernel[b]);
    }
    csv=fopen(trace,"rb");if(csv){fclose(csv);CHECK(0);}csv=fopen(trace,"wb");CHECK(csv);
    fputs("repeat,block,first,old_ms,new_ms,old_cycles,new_cycles\n",csv);
    for(repeat=0;repeat<REPEATS;++repeat){double rt[2]={0},rc[2]={0};
        for(b=0;b<profile.count;++b){state[b]=pf_state_create(kernel[b]);old[b]=reference_pf_state_create(old_kernel[b]);CHECK(state[b]&&old[b]);}
        for(at=0;at<BLOCKS+WARM;++at){double elapsed[2]={0},cost[2]={0};
            for(side=0;side<2;++side){unsigned which=(side+repeat+at)&1;double c0=cycle(),t0=now();
                for(b=0;b<profile.count;++b){const double *x=input+(size_t)b*(BLOCKS+WARM)*PF_BLOCK+at*PF_BLOCK;
                    if(which)CHECK(pf_filter_block(state[b],x,new_output[b]));else CHECK(reference_pf_filter_block(old[b],x,old_output[b]));
                }
                elapsed[which]=now()-t0;cost[which]=cycle()-c0;
            }
            CHECK(!memcmp(old_output,new_output,profile.count*sizeof old_output[0]));
            if(at>=WARM){for(side=0;side<2;++side){total[side]+=elapsed[side];cycles[side]+=cost[side];rt[side]+=elapsed[side];rc[side]+=cost[side];if(elapsed[side]>maximum[side])maximum[side]=elapsed[side];}
                fprintf(csv,"%u,%u,%u,%.17g,%.17g,%.0f,%.0f\n",repeat,at-WARM,(repeat+at)&1,elapsed[0]*1000,elapsed[1]*1000,cost[0],cost[1]);}
        }
        printf("{\"repeat\":%u,\"old_seconds\":%.12g,\"new_seconds\":%.12g,\"old_cycles\":%.0f,\"new_cycles\":%.0f,\"samples_exact\":true}\n",repeat,rt[0],rt[1],rc[0],rc[1]);fflush(stdout);
        for(b=0;b<profile.count;++b){pf_state_destroy(state[b]);reference_pf_state_destroy(old[b]);}
    }
    CHECK(!fclose(csv));for(b=0;b<profile.count;++b){pf_kernel_destroy(kernel[b]);reference_pf_kernel_destroy(old_kernel[b]);}free(input);
    printf("{\"result\":\"passed\",\"backend\":\"%s\",\"repeats\":5,\"blocks_per_repeat\":1200,\"bands\":6,\"old_seconds\":%.12g,\"new_seconds\":%.12g,\"old_cycles\":%.0f,\"new_cycles\":%.0f,\"old_max_ms\":%.9g,\"new_max_ms\":%.9g,\"samples_exact\":true,\"hard_realtime\":false}\n",pf_mac_backend(),total[0],total[1],cycles[0],cycles[1],maximum[0]*1000,maximum[1]*1000);
    return 1;
}
#endif
int main(int argc,char **argv) {
    if(!complex_cases()||!filters())return 1;
    if(argc==1){printf("FIR contracts passed: %s\n",pf_mac_backend());return 0;}
#if defined(PF_HAVE_REFERENCE) && defined(_WIN32)
    if(argc==3)return benchmark(argv[1],argv[2])?0:1;
#else
    (void)argv;
#endif
    return 2;
}
