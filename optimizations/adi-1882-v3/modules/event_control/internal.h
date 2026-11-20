#ifndef VSL_EVENT_CONTROL_INTERNAL_H
#define VSL_EVENT_CONTROL_INTERNAL_H
#include "api.h"
int ec_enqueue(EcState *state,const EcCommand *command);
void ec_cancel(EcState *state,int type);
void ec_cancel_automatic(EcState *state,int type);
void ec_start(EcState *state,unsigned type,uint64_t frame,unsigned priority,float strength);
void ec_manual_start(EcState *state,unsigned type,uint64_t frame);
void ec_afterfire_burst(EcState *state,uint64_t frame,float strength,unsigned manual);
void ec_release(EcState *state,int type,uint64_t frame,float seconds);
float ec_random(EcState *state);
#endif
