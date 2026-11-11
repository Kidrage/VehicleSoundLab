#ifndef VSL_MODAL_H
#define VSL_MODAL_H
/* A damped sine response. Pole radius is specified in physical seconds. */
typedef struct {
    double real,imag,cosine,sine,radius,hz,decay;
} VslMode;
void vsl_mode_init(VslMode *mode,double hz,double decay,double sample_rate);
void vsl_mode_strike(VslMode *mode,double amplitude,double elapsed_seconds);
double vsl_mode_tick(VslMode *mode);
#endif
