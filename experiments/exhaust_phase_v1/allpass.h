#ifndef VSL_EXPERIMENT_ALLPASS_H
#define VSL_EXPERIMENT_ALLPASS_H
typedef struct { double a1,a2,b0,z1,z2; } VslAllpass;
int vsl_allpass_init(VslAllpass *s,double rate,double hz,double q);
double vsl_allpass_tick(VslAllpass *s,double input);
#endif
