#include "internal.h"
float es_attack(uint64_t age,float seconds) {
    float t=seconds>0?(float)age/(ES_RATE*seconds):1;
    if(t>=1)return 1;
    return t*t*(3-2*t);
}
