#include "mix.h"
#include <math.h>
#include <string.h>
static int unit(double x) { return isfinite(x)&&x>=0&&x<=1; }
int hb_mix_init(HbMix *m,unsigned rate,double amount,double scale) {
    if(!m||rate!=48000||!unit(amount)||!isfinite(scale)||scale<0||scale>4)return 0;
    memset(m,0,sizeof *m);m->amount=m->target=amount;m->scale=scale;
    m->follow=1-exp(-1/(.018*rate));return 1;
}
int hb_mix_set(HbMix *m,double amount) {
    if(!m||!unit(amount))return 0;m->target=amount;return 1;
}
void hb_mix_tick(HbMix *m,const double full[2],const double low[2],double dna_env,double body_env,
    double dna[2],double body[2]) {
    unsigned c;
    m->amount+=m->follow*(m->target-m->amount);
    if(m->target==0&&m->amount<1e-12)m->amount=0;
    m->envelope+=m->follow*(body_env-m->envelope);
    for(c=0;c<2;++c) {
        /* Exact zero preserves former operations, including signed zero. */
        if(m->amount==0){dna[c]=full[c]*dna_env;body[c]=0;}
        else {
            double part=low[c]*m->amount;
            dna[c]=(full[c]-part)*dna_env;
            body[c]=part*m->envelope*m->scale;
        }
    }
    ++m->frame;
}
