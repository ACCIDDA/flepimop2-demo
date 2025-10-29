from typing import Callable, Sequence, Optional, Dict, Any

import numpy as np
from scipy.integrate import solve_ivp
from flepimop2.system import FloatArray, SystemProtocol


"""
Wrapper around scipy.integrate.solve_ivp that accepts:
- fun: callable with signature fun(t, y, **params)
- times: sequence of times at which to evaluate the solution (t_eval)
- y0: initial state (sequence)
- params: dict of extra parameters passed as keyword args to fun
- **solver_options: forwarded to scipy.integrate.solve_ivp

Returns the scipy OdeResult object.
"""

def runner(
    fun: SystemProtocol,
    times: FloatArray,
    y0: FloatArray,
    params: Optional[Dict[str, Any]] = None,
    **solver_options: Any,
) -> FloatArray:
    """
    Solve an initial value problem using scipy.solve_ivp.

    Parameters
    - fun: callable(t, y, **params) -> dy/dt
    - times: sequence of times to evaluate the solution at (t_eval). Must have length >= 2.
    - y0: initial condition (array-like)
    - params: dict of keyword parameters forwarded to fun
    - solver_options: additional keyword options forwarded to scipy.integrate.solve_ivp

    Returns
    - FloatArray (with .t and .y evaluated at `times`)
    """
    
    if times.ndim != 1:
        raise ValueError("times must be a 1D sequence of time points")

    times.sort()

    t0, tf = 0.0, times[-1]
    if times[0] < t0:
        raise ValueError("time span must not be less than zero")

    args = tuple(val for val in params.values()) if params is not None else None
    import inspect
    print(f"fun: {inspect.signature(fun)}")
    result = solve_ivp(fun, (t0, tf), y0, t_eval=times, args=args, **solver_options)
    return np.transpose(np.vstack((result.t, result.y)))
