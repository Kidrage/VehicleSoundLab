#ifndef VSL_DNA_CHARACTER_CONTROL_H
#define VSL_DNA_CHARACTER_CONTROL_H
/* Auditory design roles, not physical separation of a microphone recording. */
#define DCH_STATES 6
enum {DCH_START,DCH_IDLE,DCH_POWER,DCH_CRUISE,DCH_OVERRUN,DCH_LIMIT};
typedef struct {
    float line,air,motion,idle_blend,air_continuity,pitch_follow;
    float line_state[DCH_STATES],air_state[DCH_STATES];
} DchControl;
DchControl dch_default(void);
int dch_control_valid(const DchControl *control);
#endif
