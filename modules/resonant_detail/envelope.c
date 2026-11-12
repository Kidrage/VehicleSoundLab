#include "envelope.h"
#include <math.h>
#define RDT_PI 3.14159265358979323846
static double power(const RdtBand *m,double phase) {
    unsigned k;double v=1;
    for(k=0;k<m->envelope_order;++k)v+=cos(2*RDT_PI*(k+1)*phase)*m->beta[k];
    for(k=0;k<m->envelope_order;++k)v+=sin(2*RDT_PI*(k+1)*phase)*m->beta[m->envelope_order+k];
    return v;
}
double rdt_envelope_amplitude(const RdtBand *m,double phase) { return sqrt(power(m,phase)); }
int rdt_envelope_valid(const RdtBand *m) {
    unsigned k;double bound=0,minimum=1e300;
    if(!m||m->envelope_order>RDT_MAX_ENVELOPE)return 0;
    for(k=0;k<2*m->envelope_order;++k)if(!isfinite(m->beta[k])||fabs(m->beta[k])>4)return 0;
    for(k=0;k<m->envelope_order;++k)
        bound+=2*RDT_PI*(k+1)*(fabs(m->beta[k])+fabs(m->beta[m->envelope_order+k]));
    for(k=0;k<4096;++k) {
        double v=power(m,(double)k/4096);
        if(v<minimum)minimum=v;
    }
    /* Lipschitz correction covers all points between validation samples. */
    return minimum-bound/(2*4096)>=.05;
}
