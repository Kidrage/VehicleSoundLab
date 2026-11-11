#ifndef VSL_MODULES_H
#define VSL_MODULES_H
#include "types.h"
double vsl_clamp(double value, double lo, double hi);
void vsl_clocks_tick(VslEngine *e);
void vsl_excitation_init(VslEngine *e);
void vsl_excitation_tick(VslEngine *e,VslObjectFrame *objects);
void vsl_dna_update(VslEngine *e);
void vsl_dna_tick(VslEngine *e,double *left,double *right);
double vsl_pad_tick(VslEngine *e);
void vsl_nvh_tick(VslEngine *e,VslObjectFrame *objects);
void vsl_legacy_high_orders_tick(VslEngine *e,VslObjectFrame *objects);
void vsl_high_orders_update(VslEngine *e);
void vsl_high_orders_tick(VslEngine *e,VslObjectFrame *objects);
void vsl_mechanical_tick(VslEngine *e,VslObjectFrame *objects);
double vsl_mechanical_modal_tick(VslEngine *e);
void vsl_combustion_init(VslEngine *e,uint32_t seed);
void vsl_combustion_tick(VslEngine *e);
double vsl_ir_tick(VslEngine *e,double input);
void vsl_orchestrate(VslEngine *e,double dt);
void vsl_events_update(VslEngine *e);
double vsl_events_tick(VslEngine *e);
#endif
