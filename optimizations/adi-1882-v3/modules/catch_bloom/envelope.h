#ifndef VSL_CATCH_BLOOM_ENVELOPE_H
#define VSL_CATCH_BLOOM_ENVELOPE_H
float cb_pulse(float progress,float rise_shape,float fall_shape);
float cb_follow(float current,float target,float coefficient);
#endif
