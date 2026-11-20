#ifndef VSL_EVENT_COLOR_SPLIT_H
#define VSL_EVENT_COLOR_SPLIT_H
typedef struct { float b0,b1,b2,a1,a2,z1,z2; } VslColorLowpass;
void vsl_color_lowpass_init(VslColorLowpass *s,float rate,float hz);
float vsl_color_lowpass_tick(VslColorLowpass *s,float x);
#endif
