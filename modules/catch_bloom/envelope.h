#ifndef VSL_CATCH_BLOOM_ENVELOPE_H
#define VSL_CATCH_BLOOM_ENVELOPE_H
double cb_pulse(double progress,double rise_shape,double fall_shape);
double cb_follow(double current,double target,double coefficient);
#endif
