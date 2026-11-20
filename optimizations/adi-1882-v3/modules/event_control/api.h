#ifndef VSL_EVENT_CONTROL_API_H
#define VSL_EVENT_CONTROL_API_H
#include "event_synth/api.h"
#define EC_QUEUE 16
enum {EC_START,EC_RELEASE};
/* Ordinals deliberately adapted by vehicle_source, not a second driver. */
enum {EC_OFF,EC_READY,EC_CRANK,EC_CATCH,EC_RUNNING,EC_STOPPING};
typedef struct {
    int enabled,manual_type;
    uint64_t manual_sequence;
    float gain,pitch,decay,texture,levels[ES_TYPES];
} EcControl;
typedef struct {
    int lifecycle,shift_direction,previous_gear,allow_afterfire;
    unsigned starts,shifts,overruns;
    float rpm,load,overrun_strength;
} EcObservation;
typedef struct {uint64_t frame;unsigned operation;int type;EsRequest request;float release_seconds;unsigned manual;} EcCommand;

/* Non-RT per-engine recipe. Units are seconds; no driving eligibility override. */
typedef struct {
    unsigned afterfire_min_count,afterfire_max_count;
    float afterfire_delay_seconds,afterfire_interval_min_seconds,afterfire_interval_max_seconds;
    float afterfire_repeat_gain,afterfire_probability,afterfire_cooldown_seconds;
    float shift_delay_seconds,crank_delay_seconds;
} EcPolicy;
typedef struct {
    unsigned opportunities,bursts_attempted,unavailable,probability_skips,cooldown_skips;
} EcPolicyStats;
typedef struct {
    EcControl control;
    EcObservation last;
    EcCommand queue[EC_QUEUE];
    uint64_t next_id,manual_sequence;
    unsigned count,available_mask,overflow,cancelled,peak_queue;
    uint32_t rng;
    int initialized,enabled_seen;
    EcPolicy policy;
    EcPolicyStats policy_stats;
    uint64_t last_burst_frame;
    int has_burst;
} EcState;
EcPolicy ec_policy_default(void);
int ec_policy_valid(const EcPolicy *policy);
EcControl ec_default(void);
int ec_control_valid(const EcControl *control);
void ec_init(EcState *state,unsigned available_mask);
int ec_set(EcState *state,const EcControl *control,uint64_t frame);
void ec_observe(EcState *state,const EcObservation *observation,uint64_t frame);
int ec_poll(EcState *state,uint64_t frame,EcCommand *command);
#endif
