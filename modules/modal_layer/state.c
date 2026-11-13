#include "state.h"
#include <math.h>
#include <string.h>
int ml_state_init(MlState *out,const MlProfile *p,uint64_t seed,double amount) {
    MlState s;
    if(!out||!isfinite(amount)||amount<0||amount>1)return 0;
    memset(&s,0,sizeof s);
    if(!ml_voice_init(&s.voice,p,seed))return 0;
    s.amount=amount;s.follow=1-exp(-1/(.018*48000));*out=s;return 1;
}
int ml_state_tick(MlState *s,int gate,double amount,double envelope,MlFrame *out) {
    MlFrame f;unsigned c;
    if(!s||!out||!isfinite(amount)||amount<0||amount>1||
       !ml_voice_tick(&s->voice,gate,envelope,&f))return 0;
    s->amount+=s->follow*(amount-s->amount);
    f.weight*=s->amount;f.keep=1-f.weight;
    for(c=0;c<2;++c)f.output[c]=f.raw[c]*(envelope*f.weight*s->voice.profile->level_gain);
    *out=f;return 1;
}
