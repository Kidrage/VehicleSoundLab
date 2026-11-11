#include "render.h"
#include <stdio.h>
#include <math.h>
#include <string.h>
static SdProfile profile,analytic;static SmRender a,b;static SdVoice oscillator;
int main(int argc,char **argv){
    unsigned i,at,n;float raw[2048],out[2048],other[2048],other_out[2048];double x[2048];
    if(argc!=2||!sd_profile_load(argv[1],&profile)||!sm_render_init(&a,&profile,1000,1000,0)||!sm_render_init(&b,&profile,1000,1000,0))return 1;
    sm_render_process(&a,raw,out,1024,0);
    for(at=0;at<1024;at+=n){n=1024-at;if(n>73)n=73;sm_render_process(&b,other+at*2,other_out+at*2,n,0);}
    if(memcmp(raw,other,sizeof raw)||memcmp(out,other_out,sizeof out)||memcmp(&a.source.texture,&b.source.texture,sizeof a.source.texture))return 2;
    if(out[0]!=0||out[1]!=0)return 3;
    if(sm_render_set(&a,899,1000,0)||sm_render_set(&a,1000,1001,0)||sm_render_set(&a,1000,1000,-19))return 4;
    if(!sm_render_set(&a,1100,0,-6))return 5;
    for(i=0;i<20;++i)sm_render_process(&a,raw,out,512,0);
    if(a.source.pitch<1.099||a.source.amount>.001||fabs(a.attenuation-pow(10,-6/20.))>.001)return 6;
    sm_render_process(&a,raw,out,512,1);if(a.release!=480)return 7;
    for(i=960;i<1024;++i)if(out[i]!=0)return 8;
    analytic.rate=48000;analytic.window=1024;analytic.hop=256;analytic.harmonics=1;analytic.base_hz=46.875;
    analytic.harmonic[0].mean[0]=1;analytic.harmonic[0].mean[3]=1;
    if(!sd_voice_init(&oscillator,&analytic,48271,1.1,1,1))return 9;sd_voice_process(&oscillator,x,1024);
    for(i=0;i<1024;++i){double phase=2*3.14159265358979323846*1.1*i/1024;
        if(fabs(x[i*2]-cos(phase))>1e-11||fabs(x[i*2+1]+sin(phase))>1e-11)return 10;}
    puts("DNA: block/seed invariance, analytic stereo phase/pitch, controls, onset and stop pass");return 0;
}
