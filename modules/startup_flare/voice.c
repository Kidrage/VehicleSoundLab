#include "voice.h"
#include "model.h"
#include "core/engine.h"
#include <math.h>
#include <stdlib.h>
#define PI 3.14159265358979323846
struct SflVoice {
    ScVoice *source;
    uint64_t start,frames;
    int previous,active,cancelled;
    double amount,cancel,background,last_background;
};
static double clip(double x){return x<0?0:x>1?1:x;}
static double smooth(double x){x=clip(x);return x*x*(3-2*x);}
static double pitch(double p){
    static const double knot[]={0,.28,.60,1},value[]={.82,1.22,1.09,1};
    unsigned k=0;double u;while(k<2&&p>=knot[k+1])++k;
    u=smooth((p-knot[k])/(knot[k+1]-knot[k]));return value[k]+u*(value[k+1]-value[k]);
}
SflVoice *sfl_create(void){
    SflVoice *v=calloc(1,sizeof *v);if(!v)return NULL;
    v->source=sfl_model_create();if(!v->source){free(v);return NULL;}
    v->amount=.5;return v;
}
void sfl_destroy(SflVoice *v){if(v){sc_destroy(v->source);free(v);}}
int sfl_tick(SflVoice *v,int life,uint64_t frame,double duration,double amount,double out[2],double *background){
    double p,t,hand,x[2];unsigned c;
    if(!v||!out||!background||!isfinite(duration)||duration<=0||!isfinite(amount)||amount<0||amount>2.6)return 0;
    if(!frame)v->amount=amount;
    v->amount+=(1-exp(-1/(.018*48000)))*(amount-v->amount);
    if(life==VSL_CATCH&&v->previous!=VSL_CATCH){
        v->active=1;v->cancelled=0;v->cancel=1;v->start=frame;
        v->frames=(uint64_t)floor(duration*48000+.5);
    }
    v->previous=life;out[0]=out[1]=0;*background=life==VSL_CRANK?0:1;
    if(!v->active)return 1;
    t=(double)(frame-v->start)/v->frames;p=clip(t);
    hand=smooth((p-2./3)*3);v->background=sin(PI*.5*hand);
    if(life!=VSL_CATCH&&life!=VSL_RUNNING&&!v->cancelled){
        v->cancelled=1;v->last_background=v->background;
    }
    if(v->cancelled)v->cancel*=exp(-1/(.012*48000));
    if(!sc_tick_expression(v->source,p,t<1&&!v->cancelled,
        .05565339165321761*2.2/.25,pitch(p),1.15,.95,x))return 0;
    for(c=0;c<2;++c)out[c]=x[c]*cos(PI*.5*hand)*(2*v->amount)*v->cancel;
    *background=v->cancelled?1-(1-v->last_background)*v->cancel:v->background;
    if(t>=1||v->cancel<1e-8){
        /* Release ridge gate before the next lifecycle edge; no allocation or
           FIR recompile on retrigger. Noise state stays procedural/continuous. */
        sc_rearm(v->source);
        v->active=0;*background=1;
    }
    return 1;
}
