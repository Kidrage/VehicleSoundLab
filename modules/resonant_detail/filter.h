#ifndef VSL_RESONANT_DETAIL_FILTER_H
#define VSL_RESONANT_DETAIL_FILTER_H
#include "profile.h"
typedef struct {double ar[RDT_MAX_AR],sos[RDT_MAX_SOS][2];} RdtFilter;
double rdt_filter_source(RdtFilter *state,const RdtBand *band,double excitation);
double rdt_filter_post(RdtFilter *state,const RdtBand *band,double signal);
#endif
