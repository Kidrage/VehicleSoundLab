#include "envelope.h"
#include <math.h>
int oc_envelope_set(OcEnvelope *e,double amount) {
    if(!e||!isfinite(amount)||amount<0||amount>1)return 0;e->target=amount;return 1;
}
int oc_envelope_init(OcEnvelope *e,double amount,double seconds) {
    if(!e||!isfinite(seconds)||seconds<.005||seconds>2||!isfinite(amount)||amount<0||amount>1)return 0;
    e->amount=e->target=amount;e->follow=1-exp(-1/(48000*seconds));return 1;
}
double oc_envelope_tick(OcEnvelope *e) {e->amount+=e->follow*(e->target-e->amount);return e->amount;}
