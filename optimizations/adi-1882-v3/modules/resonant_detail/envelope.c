#include "envelope.h"
#include <math.h>
#define RDT_PI 3.14159265358979323846f
static float power(const RdtBand *m,float phase) {
    unsigned k;float v=1;
    for(k=0;k<m->envelope_order;++k)v+=cosf(2*RDT_PI*(k+1)*phase)*m->beta[k];
    for(k=0;k<m->envelope_order;++k)v+=sinf(2*RDT_PI*(k+1)*phase)*m->beta[m->envelope_order+k];
    return v;
}
float rdt_envelope_amplitude(const RdtBand *m,float phase) { return sqrtf(power(m,phase)); }
int rdt_envelope_valid(const RdtBand *m) {
    unsigned k;float bound=0,minimum=3.40282346638528859812e38f;
    if(!m||m->envelope_order>RDT_MAX_ENVELOPE)return 0;
    for(k=0;k<2*m->envelope_order;++k)if(!isfinite(m->beta[k])||fabsf(m->beta[k])>4)return 0;
    for(k=0;k<m->envelope_order;++k)
        bound+=2*RDT_PI*(k+1)*(fabsf(m->beta[k])+fabsf(m->beta[m->envelope_order+k]));
    for(k=0;k<4096;++k) {
        float v=power(m,(float)k/4096);
        if(v<minimum)minimum=v;
    }
    /* Lipschitz correction covers all points between validation samples. */
    return minimum-bound/(2*4096)>=.05f;
}
