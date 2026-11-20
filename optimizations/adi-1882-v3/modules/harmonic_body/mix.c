#include "mix.h"
#include <math.h>
#include <string.h>
static int unit(float x) { return isfinite(x)&&x>=0&&x<=1.3f; }
int hb_mix_init(HbMix *m,unsigned rate,float amount,float scale) {
    if(!m||rate!=48000||!unit(amount)||!isfinite(scale)||scale<0||scale>4)return 0;
    memset(m,0,sizeof *m);m->amount=m->target=amount;m->scale=scale;
    m->follow=1-expf(-1/(.018f*rate));return 1;
}
int hb_mix_set(HbMix *m,float amount) {
    if(!m||!unit(amount))return 0;m->target=amount;return 1;
}
void hb_mix_tick(HbMix *m,const float full[2],const float low[2],float dna_env,float body_env,
    float dna[2],float body[2]) {
    unsigned c;
    m->amount+=m->follow*(m->target-m->amount);
    if(m->target==0&&m->amount<1e-12f)m->amount=0;
    m->envelope+=m->follow*(body_env-m->envelope);
    for(c=0;c<2;++c) {
        /* Exact zero preserves former operations, including signed zero. */
        if(m->amount==0){dna[c]=full[c]*dna_env;body[c]=0;}
        else {
            float part=low[c]*m->amount;
            dna[c]=(full[c]-part)*dna_env;
            body[c]=part*m->envelope*m->scale;
        }
    }
    ++m->frame;
}
