#include "partitioned_fir/filter.h"
#include "dsp/noise.h"
#include "dsp/wave.h"
#include "vehicle_source/internal.h"
#include <math.h>
#include <stdio.h>
#define REQUIRE(x) do{if(!(x)){fprintf(stderr,"check %d: %s\n",__LINE__,#x);return 0;}}while(0)
static int noise_check(void){
    uint64_t state=731;unsigned n;double sum=0,s2=0,s4=0,lag=0;float previous=0;
    for(n=0;n<2000000;++n){float x=vsl_normal(&state);REQUIRE(isfinite(x));sum+=x;s2+=x*x;s4+=(double)x*x*x*x;lag+=x*previous;previous=x;}
    sum/=n;s2/=n;s4/=n;lag/=n;
    printf("normal: mean %.7g variance %.7g kurtosis %.7g lag1 %.7g\n",sum,s2-sum*sum,s4/(s2*s2),lag/s2);
    REQUIRE(fabs(sum)<.004&&fabs(s2-1)<.008&&fabs(s4/(s2*s2)-3)<.04&&fabs(lag/s2)<.004);
    {
        const uint32_t edge[]={UINT32_C(0x7ff7fffe),UINT32_C(0x7ff7ffff),UINT32_C(0x7ff80000),UINT32_C(0x7ffffffe),UINT32_C(0x7fffffff),UINT32_C(0xfffffffe),UINT32_C(0xffffffff),UINT32_C(0x80000000),1};
        unsigned j;
        for(j=0;j<sizeof edge/sizeof edge[0];++j){
            uint32_t seed=edge[j],y;float x;
            y=seed;for(n=0;n<7;++n)seed=y^(seed<<5);
            y=seed;for(n=0;n<3;++n)seed=y^(seed>>17);
            y=seed;for(n=0;n<3;++n)seed=y^(seed<<13);
            state=seed;x=vsl_normal(&state);REQUIRE(state==edge[j]&&isfinite(x)&&fabsf(x)<7);
        }
    }
    return 1;
}
static int fir_check(void){
    float h[512],input[1024],out[1024],maximum=0;unsigned i,j;uint64_t rng=11;
    PfKernel *k;PfState *s;
    for(i=0;i<512;++i)h[i]=.02f*vsl_normal(&rng);
    for(i=0;i<1024;++i)input[i]=vsl_normal(&rng);
    REQUIRE(k=pf_kernel_create(h,512));REQUIRE(s=pf_state_create(k));
    for(i=0;i<1024;i+=PF_BLOCK)REQUIRE(pf_filter_block(s,input+i,out+i));
    for(i=0;i<1024;++i){double y=0;for(j=0;j<512&&j<=i;++j)y+=(double)h[j]*input[i-j];
        if(fabs(y-out[i])>maximum)maximum=(float)fabs(y-out[i]);}
    pf_state_destroy(s);pf_kernel_destroy(k);printf("64-frame overlap-add vs direct convolution: max %.9g\n",maximum);REQUIRE(maximum<3e-6f);return 1;
}
static int wave_check(void){
    unsigned i;float maximum=0;
    for(i=0;i<65536;++i){float p=(float)i*(6.283185307179586f/65536);float e=fabsf(vsl_sine(p)-sinf(p));if(e>maximum)maximum=e;}
    printf("event sine lookup maximum error: %.9g\n",maximum);REQUIRE(maximum<1e-6f);return 1;
}
int main(void){
 printf("Native ABI bytes: VsEngine=%zu SaTable=%zu DrcVoice=%zu RdtVoice=%zu SaSampleCache=%zu\n",
 sizeof(VsEngine),sizeof(SaTable),sizeof(DrcVoice),sizeof(RdtVoice),sizeof(SaSampleCache));
 return noise_check()&&fir_check()&&wave_check()?0:1;
}
