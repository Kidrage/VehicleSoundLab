#include "dsp/perf.h"
#include "voice.h"
#include "model.h"
#include "core/engine.h"
#include <math.h>
#include <stdlib.h>
#include "dsp_support/storage.h"
#define PI 3.14159265358979323846f
struct SflVoice {
    ScVoice *source;
    uint64_t start,frames;
    int previous,active,cancelled;
    float amount,cancel,background,last_background,line,air;
};
VSL_STORAGE(sfl_storage,SflVoice,1,VSL_L1_VOICE)
static float clip(float x){return x<0?0:x>1?1:x;}
static float smooth(float x){x=clip(x);return x*x*(3-2*x);}
static float pitch(float p){
    static const float knot[]={0,.28f,.60f,1},value[]={.82f,1.22f,1.09f,1};
    unsigned k=0;float u;while(k<2&&p>=knot[k+1])++k;
    u=smooth((p-knot[k])/(knot[k+1]-knot[k]));return value[k]+u*(value[k+1]-value[k]);
}
SflVoice *sfl_create(void){
    SflVoice *v=sfl_storage_acquire();if(!v)return NULL;
    v->source=sfl_model_create();if(!v->source){sfl_storage_release(v);return NULL;}
    v->amount=.5f;v->line=v->air=1;return v;
}
void sfl_destroy(SflVoice *v){if(v){sc_destroy(v->source);sfl_storage_release(v);}}
void sfl_character(SflVoice *v,float line,float air){if(v){v->line=line;v->air=air;}}
int sfl_tick(SflVoice *v,int life,uint64_t frame,float duration,float amount,float out[2],float *background);
int sfl_tick_impl(SflVoice *v,int life,uint64_t frame,float duration,float amount,float out[2],float *background){
    float p,t,hand,x[2];unsigned c;
    if(!v||!out||!background||!isfinite(duration)||duration<=0||!isfinite(amount)||amount<0||amount>2.6f)return 0;
    if(!frame)v->amount=amount;
    v->amount+=(1-expf(-1/(.018f*48000)))*(amount-v->amount);
    if(life==VSL_CATCH&&v->previous!=VSL_CATCH){
        v->active=1;v->cancelled=0;v->cancel=1;v->start=frame;
        v->frames=(uint64_t)floorf(duration*48000+.5f);
    }
    v->previous=life;out[0]=out[1]=0;*background=life==VSL_CRANK?0.f:1.f;
    if(!v->active)return 1;
    t=(float)(frame-v->start)/v->frames;p=clip(t);
    /* Earlier, longer equal-power handoff retains the ongoing driven voice. */
    hand=smooth((p-.42f)/.58f);v->background=sqrtf(.04f+.96f*hand);
    if(life!=VSL_CATCH&&life!=VSL_RUNNING&&!v->cancelled){
        v->cancelled=1;v->last_background=v->background;
    }
    if(v->cancelled)v->cancel*=expf(-1/(.012f*48000));
    if(!sc_tick_expression(v->source,p,t<1&&!v->cancelled,
        .05565339165321761f*2.2f/.25f,pitch(p),1.15f*v->line,.95f*v->air,x))return 0;
    for(c=0;c<2;++c)out[c]=x[c]*sqrtf(.96f*(1-hand))*(2*v->amount)*v->cancel;
    *background=v->cancelled?1-(1-v->last_background)*v->cancel:v->background;
    if(t>=1||v->cancel<1e-8f){
        /* Release ridge gate before the next lifecycle edge; no allocation or
           FIR recompile on retrigger. Noise state stays procedural/continuous. */
        sc_rearm(v->source);
        v->active=0;*background=1;
    }
    return 1;
}
int sfl_tick(SflVoice *v,int life,uint64_t frame,float duration,float amount,float out[2],float *background){vsl_perf_enter(8);int result=sfl_tick_impl(v,life,frame,duration,amount,out,background);vsl_perf_leave();return result;}


