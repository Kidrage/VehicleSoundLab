#include "voice.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846f
static float wrap(float x){return x-floorf(x);}
static float sine(const CkVoice *v,float phase){float u=wrap(phase)*CK_TABLE;unsigned i=(unsigned)u;return v->table[i]+(u-i)*(v->table[i+1]-v->table[i]);}
static float cosine(const CkVoice *v,float phase){return sine(v,phase+.25f);}
int ck_init(CkVoice *v,const CkProfile *p,uint64_t seed){
    unsigned k,c,s;float last=0;
    if(!v||!p||!seed||!p->count||p->count>CK_MODES||!p->bands||p->bands>CK_BANDS||!isfinite(p->flutter_hz)||p->flutter_hz<2||p->flutter_hz>60||!isfinite(p->coherence)||p->coherence<0||p->coherence>1)return 0;
    for(k=0;k<p->bands;++k){float bound=0;for(c=0;c<2;++c){if(!isfinite(p->cosine[k][c])||!isfinite(p->sine[k][c]))return 0;bound+=fabsf(p->cosine[k][c])+fabsf(p->sine[k][c]);}if(bound>.85f)return 0;}
    for(k=0;k<p->count;++k){const CkMode *m=p->mode+k;
        if(!isfinite(m->hz)||m->hz<=last||m->hz>9000||!isfinite(m->width_hz)||m->width_hz<1||m->width_hz>150||m->band>=p->bands)return 0;last=m->hz;
        for(c=0;c<2;++c){if(!isfinite(m->phase[c])||fabsf(m->phase[c])>100000)return 0;for(s=0;s<3;++s)if(!isfinite(m->amplitude[s][c])||m->amplitude[s][c]<0||m->amplitude[s][c]>2)return 0;}
    }
    memset(v,0,sizeof *v);v->profile=*p;rdt_excitation_init(&v->rng,seed^UINT64_C(0x243f6a8885a308d3));
    for(k=0;k<=CK_TABLE;++k)v->table[k]=sinf(2*PI*k/CK_TABLE);
    for(s=0;s<CK_HOP;++s)v->weight[s]=.5f-.5f*cosf(PI*(float)s/CK_HOP);
    for(k=0;k<p->count;++k){v->alpha[k]=expf(-PI*p->mode[k].width_hz*CK_HOP/48000);v->innovation[k]=sqrtf(1-v->alpha[k]*v->alpha[k]);
        /* The exact same finite interpolation cycle repeats. Cache its
           normalization, not the random states or audible envelopes. */
        for(s=0;s<CK_HOP;++s){float w=v->weight[s];v->variance[k][s]=sqrtf((1-w)*(1-w)+w*w+2*v->alpha[k]*w*(1-w));}
        v->initial_phase[k]=wrap(.1f*rdt_excitation_next(&v->rng)/(2*PI));v->phase[k]=v->initial_phase[k];
        for(c=0;c<2;++c){v->offset[k][c]=p->mode[k].phase[c]/(2*PI);v->unit[k][c][0]=cosf(p->mode[k].phase[c]);v->unit[k][c][1]=sinf(p->mode[k].phase[c]);v->left[k][c]=rdt_excitation_next(&v->rng);v->right[k][c]=v->alpha[k]*v->left[k][c]+v->innovation[k]*rdt_excitation_next(&v->rng);}
    }return 1;
}
int ck_tick(CkVoice *v,float progress,int gate,float pitch,float motion,float out[2],float *air){
    float amplitude[CK_BANDS],sum[2]={0},u,w,variance,blend,coherent,random,air_sum=0,cl[2],sl[2];unsigned k,c,stage;
    if(!v||!out||!v->profile.count||!isfinite(progress)||progress<0||progress>1||(gate!=0&&gate!=1)||!isfinite(pitch)||pitch<.5f||pitch>2||!isfinite(motion)||motion<0||motion>1)return 0;
    if(gate&&!v->previous_gate){v->clock=0;for(k=0;k<v->profile.count;++k)v->phase[k]=v->initial_phase[k];}
    /* Common irregular acoustic drive, not a claimed physical shaft clock. */
    if(!v->position)v->roughness=.90f*v->roughness+sqrtf(1-.90f*.90f)*rdt_excitation_next(&v->rng);
    v->clock=wrap(v->clock+v->profile.flutter_hz/48000*(.96f+.04f*pitch)*(1+.035f*tanhf(v->roughness)));
    for(c=0;c<2;++c){cl[c]=cosine(v,(c+1)*v->clock);sl[c]=sine(v,(c+1)*v->clock);}
    for(k=0;k<v->profile.bands;++k){float a=1;for(c=0;c<2;++c)a+=motion*(v->profile.cosine[k][c]*cl[c]+v->profile.sine[k][c]*sl[c]);amplitude[k]=a;air_sum+=a;}
    u=progress*2;stage=(unsigned)u;if(stage>1)stage=1;blend=u-stage;blend=blend*blend*(3-2*blend);
    w=v->weight[v->position];coherent=sqrtf(v->profile.coherence);random=sqrtf((1-v->profile.coherence)/2);
    for(k=0;k<v->profile.count;++k){const CkMode *m=v->profile.mode+k;float re,im,cp=cosine(v,v->phase[k]),sp=sine(v,v->phase[k]);variance=v->variance[k][v->position];
        re=coherent+random*((1-w)*v->left[k][0]+w*v->right[k][0])/variance;im=random*((1-w)*v->left[k][1]+w*v->right[k][1])/variance;
        for(c=0;c<2;++c){float co=v->unit[k][c][0],si=v->unit[k][c][1],a=m->amplitude[stage][c]+blend*(m->amplitude[stage+1][c]-m->amplitude[stage][c]);sum[c]+=a*amplitude[m->band]*((re*co-im*si)*cp-(re*si+im*co)*sp);}
        v->phase[k]=wrap(v->phase[k]+m->hz*pitch/48000);
    }
    if(++v->position==CK_HOP){v->position=0;for(k=0;k<v->profile.count;++k)for(c=0;c<2;++c){v->left[k][c]=v->right[k][c];v->right[k][c]=v->alpha[k]*v->left[k][c]+v->innovation[k]*rdt_excitation_next(&v->rng);}}
    if(air)*air=air_sum/v->profile.bands;out[0]=sum[0];out[1]=sum[1];v->previous_gate=gate;++v->frame;return 1;
}
