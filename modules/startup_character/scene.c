#include "scene.h"
#include <math.h>
#define PI 3.14159265358979323846
static double clip(double x){return x<0?0:x>1?1:x;}
static double smooth(double x){x=clip(x);return x*x*(3-2*x);}
static double pitch(const ScGesture *g,double p){
    unsigned k=0;double u;while(k+2<g->count&&p>=g->knot[k+1])++k;
    u=smooth((p-g->knot[k])/(g->knot[k+1]-g->knot[k]));
    return (1-u)*g->pitch[k]+u*g->pitch[k+1];
}
int sc_timeline_valid(const ScTimeline *t){
    unsigned k,j;double duration=0;
    if(!t||!isfinite(t->start)||t->start<0||t->start>10||!isfinite(t->handoff)||t->handoff<=0||!isfinite(t->reference_gain)||t->reference_gain<0||t->reference_gain>1||!isfinite(t->rotation_scale)||t->rotation_scale<0||t->rotation_scale>3)return 0;
    for(k=0;k<3;++k){const ScGesture *g=t->gesture+k;
        if(!isfinite(t->duration[k])||t->duration[k]<.05||t->duration[k]>10||!isfinite(g->level)||g->level<0||g->level*t->reference_gain>4||!isfinite(g->core)||g->core<0||g->core>3||!isfinite(g->texture)||g->texture<0||g->texture>3||g->count<2||g->count>4||g->knot[0]!=0||g->knot[g->count-1]!=1)return 0;
        for(j=0;j<g->count;++j)if(!isfinite(g->knot[j])||(j&&g->knot[j]<=g->knot[j-1])||!isfinite(g->pitch[j])||g->pitch[j]<.5||g->pitch[j]>2)return 0;
        duration+=t->duration[k];
    }return t->handoff<=t->duration[2]&&duration<=30;
}
int sc_mix_scene(ScVoice *const voice[3],const ScTimeline *t,uint64_t first,
                 const float *base,float *mix,float *parts,unsigned frames){
    unsigned n,k,c;double start[3],stop[3],end;
    if(!voice||!voice[0]||!voice[1]||!voice[2]||!base||!mix||frames>1024||first>UINT64_C(48000)*600||!sc_timeline_valid(t))return 0;
    start[0]=t->start;for(k=0;k<3;++k){stop[k]=start[k]+t->duration[k];if(k<2)start[k+1]=stop[k];}end=stop[2];
    for(n=0;n<frames;++n){
        double time=(double)(first+n)/48000,hand=smooth((time-(end-t->handoff))/t->handoff);
        double dna_weight=sin(PI*.5*hand),catch_weight=time>=end?0:cos(PI*.5*hand);
        float stem[4][2],sum[2]={0};
        for(k=0;k<3;++k){
            const ScGesture *g=t->gesture+k;double x[2],p=clip((time-start[k])/t->duration[k]);
            double weight=k==2?catch_weight:1-smooth((time-(stop[k]-.035))/.035);
            int gate=time>=start[k]-1e-10&&time<stop[k]-1e-10;
            if(!sc_tick_expression(voice[k],p,gate,t->reference_gain*g->level,pitch(g,p),g->core,g->texture,x))return 0;
            for(c=0;c<2;++c){
                /* Match frozen review: C sample -> float, apply weight/scale,
                   then float stems and sum in their original order. */
                float raw=(float)x[c];double y=(double)raw*weight;
                if(k==1)y*=t->rotation_scale;
                stem[k][c]=(float)y;sum[c]+=stem[k][c];
            }
        }
        for(c=0;c<2;++c){stem[3][c]=(float)(base[2*n+c]*dna_weight);sum[c]+=stem[3][c];mix[2*n+c]=sum[c];}
        if(parts)for(k=0;k<4;++k)for(c=0;c<2;++c)parts[8*n+2*k+c]=stem[k][c];
    }return 1;
}
