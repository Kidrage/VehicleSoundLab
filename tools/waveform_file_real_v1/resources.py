"""New shape budgets retain the original reserves and count all three panels."""
from waveform_file_full_v1.resources import preflight as original


def preflight(directory,N,M,H,block):
    result=original(directory,N=N,M=M,H=H,block=block)
    n,k=2*M*H,min(N,2*M*H)
    phases=result['major_phase_panel_arithmetic']
    result['previous_two_panel_graph_transpose_arithmetic']=phases['graph_transpose']
    phases['graph_transpose']=32768*N+8*k*block+24*n*block
    main=max(phases.values())+result['resident_misc_allowance']
    result['main_phase_array_allowance']=main
    result['required_available']=main+result['native_temporary_allowance']+result['headroom_guard']
    result['memory_passed']=min(result['available_physical_bytes'],result['available_commit_bytes'])>=result['required_available']
    result['graph_transpose_three_owned_panels_counted']=True
    return result
