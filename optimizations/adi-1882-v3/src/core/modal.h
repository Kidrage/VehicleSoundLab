#ifndef VSL_MODAL_H
#define VSL_MODAL_H
/* A damped sine response. Pole radius is specified in physical seconds. */
typedef struct {
    float real,imag,cosine,sine,radius,hz,decay;
} VslMode;
void vsl_mode_init(VslMode *mode,float hz,float decay,float sample_rate);
void vsl_mode_strike(VslMode *mode,float amplitude,float elapsed_seconds);
float vsl_mode_tick(VslMode *mode);
#endif
