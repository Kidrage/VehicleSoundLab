#ifndef VSL_FIRING_PROFILE_H
#define VSL_FIRING_PROFILE_H
/* Crank angles describe combustion timing, never acoustic propagation delay.
   Index is chronological event index, not physical cylinder number. */
double vsl_firing_degrees(int profile,int event,int cylinders);
double vsl_bank_offset_cycles(int profile);
#endif
