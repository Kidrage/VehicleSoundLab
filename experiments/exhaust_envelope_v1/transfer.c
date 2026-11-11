#include "transfer.h"
#include "profile.h"
#include <math.h>
#include <string.h>
int vsl_envelope_init(VslEnvelopeTransfer *s,double rate,int mode) {
    int side,k;memset(s,0,sizeof *s);
    if(mode<0||mode>2||!isfinite(rate)||rate<16000||rate>192000)return 0;
    s->sample_rate=rate;s->mode=mode;s->eligible=1;
    for(side=0;side<2;++side)for(k=0;k<3;++k) {
        const VslEnvelopeBand *p=vsl_envelope_band(k);
        if(!vsl_envelope_bell(&s->bank[side][k],rate,p->hz,p->q,p->gain_db*vsl_envelope_strength(mode)))return 0;
    }
    return 1;
}
void vsl_envelope_prepare(VslEnvelopeTransfer *s,const VslEngine *e) {
    int eligible=e->smooth.profile==VSL_V10&&!e->dna.custom_count&&!e->target.pure_osc;
    if(eligible!=s->eligible) {
        int side,k;for(side=0;side<2;++side)for(k=0;k<3;++k)s->bank[side][k].z1=s->bank[side][k].z2=0;
        s->eligible=eligible;
    }
}
double vsl_envelope_side_tick(VslEnvelopeTransfer *s,int side,double x) {
    int k;if(!s->mode||!s->eligible||side<0||side>1)return x;
    for(k=0;k<3;++k)x=vsl_envelope_biquad_tick(&s->bank[side][k],x);
    return x;
}
