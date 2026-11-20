#include "ridge.h"
#include "resonant_detail/excitation.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846f
int sc_ridge_init(ScRidgeVoice *v,const ScRidge *r,unsigned count,unsigned frames,float variation,float pitch,uint64_t seed){
    unsigned k,c;RdtExcitation rng;
    if(!v||!r||!count||count>SC_RIDGES||!frames||!seed||!isfinite(variation)||variation<0||variation>1||!isfinite(pitch)||pitch<.5f||pitch>2)return 0;
    for(k=0;k<count;++k){
        float finish=r[k].hz+r[k].slew*r[k].frames/48000;
        if(r[k].frames<16||r[k].start_frame>frames||r[k].frames>frames-r[k].start_frame||
           !isfinite(r[k].hz)||!isfinite(r[k].slew)||r[k].hz*pitch<30||r[k].hz*pitch>18000||finish*pitch<30||finish*pitch>18000)return 0;
        for(c=0;c<2;++c)if(!isfinite(r[k].amplitude[c])||r[k].amplitude[c]<0||r[k].amplitude[c]>2||!isfinite(r[k].phase[c]))return 0;
    }
    memset(v,0,sizeof *v);v->count=count;v->reference_frames=frames;memcpy(v->data,r,count*sizeof *r);
    rdt_excitation_init(&rng,seed^UINT64_C(0x6a09e667f3bcc909));
    for(k=0;k<count;++k){
        float jitter=variation*tanhf(rdt_excitation_next(&rng)),phase=variation*tanhf(rdt_excitation_next(&rng));
        v->pitch[k]=pitch*(1+.012f*jitter);v->gain[k]=1+jitter;
        for(c=0;c<2;++c)v->data[k].phase[c]+=phase;
    }
    return 1;
}
static void tick(ScRidgeVoice *v,float progress,int gate,float pitch,float out[2]){
    unsigned k,c;float position=progress*v->reference_frames;out[0]=out[1]=0;
    if(gate&&!v->previous_gate)memset(v->active,0,sizeof v->active);
    for(k=0;k<v->count;++k){
        const ScRidge *r=v->data+k;float local=position-r->start_frame;
        if(local< -1e-7f||local>=r->frames){v->active[k]=0;continue;}
        if(local<0)local=0;
        float t=local/48000,hz=(r->hz+r->slew*t)*v->pitch[k]*pitch;
        float envelope=.5f-.5f*cosf(2*PI*local/r->frames);
        if(!v->active[k]){
            for(c=0;c<2;++c)v->phase[k][c]=r->phase[c]+2*PI*v->pitch[k]*pitch*(r->hz*t+.5f*r->slew*t*t);
            v->active[k]=1;
        }else for(c=0;c<2;++c)v->phase[k][c]+=PI*(v->previous_hz[k]+hz)/48000;
        v->previous_hz[k]=hz;
        for(c=0;c<2;++c)out[c]+=envelope*v->gain[k]*r->amplitude[c]*cosf(v->phase[k][c]);
    }
    v->previous_gate=gate;
}
void sc_ridge_tick(ScRidgeVoice *v,float progress,int gate,float out[2]){tick(v,progress,gate,1,out);}
int sc_ridge_tick_pitch(ScRidgeVoice *v,float progress,int gate,float pitch,float out[2]){
    unsigned k;
    if(!v||!out||!isfinite(progress)||progress<0||progress>1||(gate!=0&&gate!=1)||!isfinite(pitch)||pitch<.5f||pitch>2)return 0;
    for(k=0;k<v->count;++k){
        const ScRidge *r=v->data+k;float local=progress*v->reference_frames-r->start_frame;
        if(local>=0&&local<r->frames){float hz=(r->hz+r->slew*local/48000)*v->pitch[k]*pitch;if(hz<20||hz>20000)return 0;}
    }
    tick(v,progress,gate,pitch,out);return 1;
}
