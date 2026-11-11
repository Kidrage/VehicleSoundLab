#include "render.h"
#include <stdio.h>
#include <math.h>
#include <string.h>
static SdProfile dna;static LrProfile low;static SmRender a,b;static SdVoice reference;static LrVoice low_a,low_b;
int main(int argc,char **argv){unsigned i,at,n;float raw[2048],out[2048],other[2048],other_out[2048],body[1024],other_body[1024];double expected[2048],mono[1024];
    if(argc!=3||!sd_profile_load(argv[1],&dna)||!lr_profile_load(argv[2],&low)||
       !sm_render_init(&a,&dna,&low,1000,1000,0,600,0)||!sm_render_init(&b,&dna,&low,1000,1000,0,600,0))return 1;
    sm_render_process(&a,raw,body,out,1024,0);
    for(at=0;at<1024;at+=n){n=1024-at;if(n>73)n=73;sm_render_process(&b,other+at*2,other_body+at,other_out+at*2,n,0);}
    if(memcmp(raw,other,sizeof raw)||memcmp(body,other_body,sizeof body)||memcmp(out,other_out,sizeof out))return 2;
    if(!sd_voice_init(&reference,&dna,SM_SEED,1,1,1))return 3;sd_voice_process(&reference,expected,1024);
    for(i=0;i<2048;++i)if(raw[i]!=(float)expected[i])return 4;
    if(out[0]!=0||out[1]!=0||sm_render_set(&a,899,1000,0,600,0)||sm_render_set(&a,1000,1000,0,1001,0)||sm_render_set(&a,1000,1000,0,600,3))return 5;
    /* Zero low amount is an exact bypass, with the independent cloud kept hot. */
    if(!sm_render_init(&b,&dna,&low,1000,1000,0,0,0))return 6;sm_render_process(&b,other,body,other_out,1024,0);
    for(i=0;i<1024;++i){double env=i<240?i/239.:1;if(body[i]!=0)return 7;
        for(n=0;n<2;++n)if(other_out[2*i+n]!=(float)(expected[2*i+n]*.5*env))return 8;}
    if(!lr_voice_init(&low_a,&low,1,1,0)||!lr_voice_init(&low_b,&low,1,1,1))return 9;
    lr_voice_process(&low_a,mono,1024);lr_voice_process(&low_b,mono,1024);
    if(memcmp(&low_a.cloud,&low_b.cloud,sizeof low_a.cloud))return 10;
    if(!sm_render_set(&a,1100,0,-6,1000,2))return 11;
    for(i=0;i<20;++i)sm_render_process(&a,raw,body,out,512,0);
    if(a.source.pitch<1.099||a.rumble.pitch<1.099||a.source.amount>.001||a.rumble.amount<.999||a.dna_mix>.001)return 12;
    sm_render_process(&a,raw,body,out,512,1);if(a.release!=480)return 13;
    for(i=960;i<1024;++i)if(out[i]!=0)return 14;
    puts("DNA unchanged; low zero bypass, block/RNG independence, controls, source solo and stop pass");return 0;
}
