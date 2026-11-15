"""Identical stable square-root calculations with optional disk-mapped basis storage."""
from pathlib import Path
import numpy as np
from observer_representer_v1.primal import PenaltyPrimal
from observer_representer_v1.dual import representer_certificate
from observer_inverse_v1.fit import complex_array
from observer_frequency_v1.optimality import bound
from .reorth import orthogonalize
from .stable_residual import estimate


def solve(operator, rhs, accept, maxiter=4000, atol=1e-11, btol=1e-11, conlim=1e12, basis_directory=None):
    m, n = operator.shape
    capacity = min(n, maxiter)
    if basis_directory is None:
        U, V = np.empty((m, capacity+1), order='F'), np.empty((n, capacity), order='F')
    else:
        basis_directory = Path(basis_directory).resolve()
        basis_directory.mkdir(parents=True, exist_ok=False)
        U = np.memmap(basis_directory/'U.bin', dtype='float64', mode='w+', shape=(m, capacity+1), order='F')
        V = np.memmap(basis_directory/'V.bin', dtype='float64', mode='w+', shape=(n, capacity), order='F')
    H = np.zeros((capacity+1, capacity))
    beta0 = float(np.linalg.norm(rhs))
    if not beta0:
        raise ValueError('Frozen fitting controls require nonzero rhs')
    U[:, 0] = rhs/beta0
    candidate = operator.rmatvec(U[:, 0])
    uc, vc = 1, 0
    threshold = 64*np.finfo(float).eps
    checkpoints = []
    capture, info = None, None
    def evaluate():
        capture, info = estimate(H[:uc, :vc], U[:, :uc], V[:, :vc], rhs,
            operator.rmatvec, operator.matvec)
        condition = float(np.linalg.cond(H[:uc, :vc]))
        compatible = info['stable_residual_norm'] <= btol*beta0+atol*info['projected_Frobenius_estimate']*float(np.linalg.norm(capture['z']))
        stop = 1 if compatible else 2 if info['stable_normal_relative'] <= atol else 3 if condition >= conlim else 7
        estimated_stop = stop
        guard = info['relative_backward_discrepancy'] <= atol
        original = accept(capture['z'])
        accepted = bool(stop in (1, 2) and guard and original['qualified'])
        if stop in (1, 2) and not accepted:
            stop = 7
        info.update(directions=vc, stop=stop, estimated_stop_before_original_guards=estimated_stop,
            accepted=accepted, projected_condition=condition,
            backward_discrepancy_guard_passed=guard, original_checks=original)
        checkpoints.append(info.copy())
        return capture, info
    status = 'dimension_or_iteration_limit'
    for j in range(capacity):
        residual, _ = orthogonalize(candidate, V[:, :vc])
        alpha = float(np.linalg.norm(residual))
        if alpha <= threshold*float(np.linalg.norm(candidate)):
            status = 'adjoint_near_breakdown'
            break
        V[:, j] = residual/alpha
        vc += 1
        raw = operator.matvec(V[:, j])
        residual, h = orthogonalize(raw, U[:, :uc])
        H[:uc, j] = h
        beta = float(np.linalg.norm(residual))
        near = beta <= threshold*float(np.linalg.norm(raw))
        if not near:
            H[uc, j] = beta
            U[:, uc] = residual/beta
            uc += 1
        if vc % 8 == 0 or near or vc == capacity:
            capture, info = evaluate()
            if info['accepted'] or info['stop'] == 3:
                status = 'stable_rule_and_original_guards' if info['accepted'] else 'condition_limit'
                break
        if near:
            status = 'forward_near_breakdown'
            break
        candidate = operator.rmatvec(U[:, uc-1])
    if not vc:
        raise ArithmeticError('No right Krylov direction')
    if info is None or info['directions'] != vc:
        capture, info = evaluate()
    capture.update(U=U[:, :uc], V=V[:, :vc], H=H[:uc, :vc], rhs=rhs,
        U_gram=U[:, :uc].T@U[:, :uc], V_gram=V[:, :vc].T@V[:, :vc])
    info.update(basis_storage='RAM' if basis_directory is None else 'mapped_float64_Fortran',
        basis_directory=None if basis_directory is None else str(basis_directory),
        basis_shapes=dict(U=list(U[:, :uc].shape), V=list(V[:, :vc].shape)))
    info.update(solver='stable_QR_two_sided_square_root_projection', scipy_LSMR=False,
        iterations=vc, status=status, atol=atol, btol=btol, conlim=conlim, maxiter=maxiter,
        checkpoints=checkpoints, full_adjoint_includes_outside_subspace=True,
        original_checks_mandatory=True, stable_normal_is_estimate_not_exact_full_bound=True)
    return capture['z'], info, capture


def infer(system, audio, basis_directory=None):
    op = PenaltyPrimal(system)
    rhs = np.r_[system.rhs(audio)[:system.ysize], np.zeros(system.nsize)]
    def original(z):
        x = op.prior.apply(z)
        nodes = complex_array(x, system.nshape)*system.scale[None]
        residual = system@x-system.rhs(audio)
        u = -residual[:system.ysize]
        gradient = float(np.linalg.norm(system.rmatvec(residual))/max(np.linalg.norm(system.rmatvec(system.rhs(audio))), 1e-24))
        rc, pc = bound(system, audio, nodes), representer_certificate(system, audio, nodes, u)
        return nodes, u, gradient, rc, pc
    def accept(z):
        _, _, gradient, rc, pc = original(z)
        return dict(relative_stationarity=gradient, residual_gap_passed=rc['additional_gap_gate_passed'],
            representer_gap_passed=pc['additional_gap_gate_passed'],
            qualified=bool(gradient < 2e-7 and rc['additional_gap_gate_passed'] and pc['additional_gap_gate_passed']))
    z, info, capture = solve(op, rhs, accept, basis_directory=basis_directory)
    nodes, u, gradient, rc, pc = original(z)
    info.update(relative_stationarity=gradient, objective=rc['primal'], same_original_objective=True,
        converged=bool(info['accepted'] and gradient < 2e-7 and rc['additional_gap_gate_passed'] and pc['additional_gap_gate_passed']))
    return nodes, u, info, rc, pc, capture


def release_basis(capture, info):
    """Close mappings, then trim only their verified task-owned raw files."""
    directory = Path(info['basis_directory']).resolve()
    for name in ('U', 'V'):
        path = (directory/(name+'.bin')).resolve()
        assert path.parent == directory and path.name in ('U.bin', 'V.bin')
        expected = int(np.prod(info['basis_shapes'][name]))*8
        mapped = capture.pop(name)
        mapped.flush()
        mapped._mmap.close()
        with path.open('r+b') as stream:
            stream.truncate(expected)
        assert path.stat().st_size == expected
