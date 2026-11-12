#ifndef VSL_RESONANT_DETAIL_EXCITATION_H
#define VSL_RESONANT_DETAIL_EXCITATION_H
#include <stdint.h>
typedef struct {uint64_t state;double spare;unsigned has_spare;} RdtExcitation;
void rdt_excitation_init(RdtExcitation *state,uint64_t seed);
double rdt_excitation_next(RdtExcitation *state);
#endif
