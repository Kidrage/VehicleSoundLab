#include "filter.h"
/* Transposed direct form II, preserving scipy lfilter/sosfilt operation order. */
double rdt_filter_source(RdtFilter *s,const RdtBand *m,double noise) {
    unsigned i;double y=m->sigma*noise+s->ar[0];
    for(i=0;i+1<m->order;++i)s->ar[i]=s->ar[i+1]-m->a[i+1]*y;
    s->ar[m->order-1]=-m->a[m->order]*y;
    return y;
}
double rdt_filter_post(RdtFilter *s,const RdtBand *m,double x) {
    unsigned i;
    for(i=0;i<m->sections;++i) {
        const double *a=m->sos[i];double y=a[0]*x+s->sos[i][0];
        s->sos[i][0]=a[1]*x-a[4]*y+s->sos[i][1];
        s->sos[i][1]=a[2]*x-a[5]*y;x=y;
    }
    return x;
}
