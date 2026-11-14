#ifndef VSL_DRIVER_STAGE_COST_TIMING_H
#define VSL_DRIVER_STAGE_COST_TIMING_H
#include <stdint.h>
enum {SP_MAIN,SP_SHAPE,SP_LOW,SP_RESONANCE,SP_IDLE,SP_RESIDUAL,SP_AUX,SP_BODY,SP_SPATIAL,SP_DRIVE,SP_ORCHESTRATE,SP_EMPTY,SP_COUNT};
typedef struct {uint64_t calls,ticks;} SpMetric;
extern SpMetric sp_metrics[SP_COUNT];
extern const char *sp_names[SP_COUNT];
uint64_t sp_begin(void);
void sp_end(unsigned stage,uint64_t before);
uint64_t sp_frequency(void);
void sp_reset(void);
#endif
