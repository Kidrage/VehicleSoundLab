#ifndef VSL_LAYER_MONITOR_LAYERS_H
#define VSL_LAYER_MONITOR_LAYERS_H
/* Engineering dry stereo buses, not separated physical cylinders/microphones. */
enum { LM_DNA,LM_LOW,LM_DETAIL,LM_AUX,LM_EVENTS,LM_OTHER,LM_LAYERS };
#define LM_SAMPLES (LM_LAYERS*2)
#define LM_SELECTIONS (LM_LAYERS+1) /*0 canonical full presentation,1..6 dry buses. */
#endif
