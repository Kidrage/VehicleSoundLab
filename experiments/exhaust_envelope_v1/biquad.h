#ifndef VSL_ENVELOPE_BIQUAD_H
#define VSL_ENVELOPE_BIQUAD_H
typedef struct { double b0,b1,b2,a1,a2,z1,z2; } VslEnvelopeBiquad;
int vsl_envelope_bell(VslEnvelopeBiquad *s,double rate,double hz,double q,double gain_db);
double vsl_envelope_biquad_tick(VslEnvelopeBiquad *s,double input);
#endif
