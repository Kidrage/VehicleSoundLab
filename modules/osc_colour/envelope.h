#ifndef VSL_OSC_COLOUR_ENVELOPE_H
#define VSL_OSC_COLOUR_ENVELOPE_H
typedef struct {double amount,target,follow;} OcEnvelope;
int oc_envelope_init(OcEnvelope *envelope,double amount,double seconds);
int oc_envelope_set(OcEnvelope *envelope,double amount);
double oc_envelope_tick(OcEnvelope *envelope);
#endif
