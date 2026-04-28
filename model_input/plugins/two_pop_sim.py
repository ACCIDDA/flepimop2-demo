"""Helper to run multi-state simulations (e.g., two-pop SIR) via flepimop2 builders."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from flepimop2.backend.abc import build as build_backend
from flepimop2.configuration import ConfigurationModel
from flepimop2.engine.abc import build as build_engine
from flepimop2.meta import RunMeta
from flepimop2.parameter.abc import build as build_parameter
from flepimop2.system.abc import build as build_system

USAGE = "python model_input/plugins/two_pop_sim.py <config.yml> [simulate_name]"
MIN_ARGS = 1
MAX_ARGS = 2


def _initial_key(param_block: dict[str, object], state: str) -> str:
    k1 = f"{state.lower()}_0"
    k2 = f"{state.lower()}0"
    if k1 in param_block:
        return k1
    if k2 in param_block:
        return k2
    msg = f"Missing initial parameter for state {state!r} (tried {k1}, {k2})"
    raise KeyError(msg)


def _build_initials(
    config_model: ConfigurationModel, state_names: list[str]
) -> np.ndarray:
    params = config_model.parameters
    vals = []
    for state in state_names:
        key = _initial_key(params, state)
        vals.append(build_parameter(params[key]).sample().item())
    return np.asarray(vals, dtype=np.float64)


def _strip_initials(
    config_model: ConfigurationModel, state_names: list[str]
) -> dict[str, float]:
    initial_keys = {f"{s.lower()}_0" for s in state_names} | {
        f"{s.lower()}0" for s in state_names
    }
    params: dict[str, float] = {}
    for name, p_cfg in config_model.parameters.items():
        if name.lower() in initial_keys:
            continue
        params[name] = build_parameter(p_cfg).sample().item()
    return params


def main() -> None:
    """Run a multi-state simulate target and persist its CSV via backend."""
    args = sys.argv[1:]
    if not (MIN_ARGS <= len(args) <= MAX_ARGS):
        raise SystemExit(USAGE)

    cfg_path = Path(args[0])
    sim_name_override = args[1] if len(args) == MAX_ARGS else None

    config_model = ConfigurationModel.from_yaml(cfg_path)
    simulate_block = config_model.simulate
    if not simulate_block:
        msg = "config.simulate must be non-empty"
        raise ValueError(msg)

    if sim_name_override is None:
        sim_name, simulate_cfg = next(iter(simulate_block.items()))
    else:
        simulate_cfg = simulate_block.get(sim_name_override)
        if simulate_cfg is None:
            msg = f"simulate target {sim_name_override!r} not found"
            raise KeyError(msg)
        sim_name = sim_name_override

    system_cfg = config_model.systems[simulate_cfg.system].model_dump()
    engine_cfg = config_model.engines[simulate_cfg.engine].model_dump()
    backend_cfg = config_model.backends[simulate_cfg.backend].model_dump()

    state_names = system_cfg["spec"]["state"]
    y0 = _build_initials(config_model, state_names)
    params = _strip_initials(config_model, state_names)

    system = build_system(system_cfg)
    engine = build_engine(engine_cfg)
    backend = build_backend(backend_cfg)

    result = engine.run(system, simulate_cfg.t_eval, y0, params)
    backend.save(result, RunMeta(name=sim_name))
    msg = f"Saved simulation '{sim_name}' with {len(state_names)} states"
    sys.stdout.write(msg + "\n")


if __name__ == "__main__":
    main()
