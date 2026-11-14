#include "split.h"
void lm_split(const LmSources *s,float out[LM_SAMPLES]) {
    int c;
    for(c=0;c<2;++c) {
        double core=s->dna[c],detail=s->residual[c]+s->resonant[c],other=s->added[c];
        if(s->fine_idle){core+=s->idle_modal[c]*s->idle_scale;detail+=s->idle_detail[c]*s->idle_scale;other=0;}
        out[2*LM_DNA+c]=(float)(core*s->gain);
        out[2*LM_LOW+c]=(float)((s->body[c]+s->coherent[c])*s->gain);
        out[2*LM_DETAIL+c]=(float)(detail*s->gain);
        out[2*LM_AUX+c]=(float)(s->aux[c]*s->gain);
        out[2*LM_EVENTS+c]=(float)((s->event+s->starter[c]+s->catch_delta[c])*s->gain);
        out[2*LM_OTHER+c]=(float)(other*s->gain);
    }
}
