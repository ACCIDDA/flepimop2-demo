# `flepimop2` Demo

This repository contains a demonstration project designed to introduce users to the `flepimop2` simulation framework. The demo starts from a fully handwritten SIR model and solver, then progresses to using the `op_engine` integration to run simulations through the same `flepimop2` engine interface.

The goal is to illustrate:

- How to define systems and solvers manually
- How to configure and run simulations
- How to add postprocessing steps
- How to swap solver backends (handwritten -> `op_engine`) without changing the model definition
- How `flepimop2` composes simulation pipelines from modular components
- How heterogeneous postprocessing workflows (R + Python) can coexist

------------------------------------------------------------------------

## Installation

To create a conda environment containing `flepimop2`, `op_engine`, the `flepimop2-op-engine` adapter, and all demo dependencies, run:

<!-- skip-test -->
```bash
just venv
conda activate ./venv
```

This creates a local environment under `./venv/` using `environment.yaml`.

------------------------------------------------------------------------

## R Dependencies (Postprocessing)

Some postprocessing examples in this repository use R-based scripts.

### `air` (R formatter/linter) is a separate tool

This repository uses [`air`](https://posit-dev.github.io/air/) to format and lint R code (e.g., in `postprocessing/`). **Unlike the other linting tools used by this repo, `air` cannot be managed via `conda`** because it is **not an R package** (i.e., it is not installed with `install.packages()`); it is a standalone command-line tool.

See the `air` CLI documentation:  
https://posit-dev.github.io/air/cli.html

### Installing `air`

#### macOS (Homebrew)

<!-- skip-test -->
```bash
brew install r-air
```

#### Other platforms

Install `air` from the official release artifacts and ensure the `air` binary is available on your `PATH`:

https://github.com/posit-dev/air/releases

### Verify installation

<!-- skip-test -->
```bash
air --version
```

------------------------------------------------------------------------

## Development Installation Overrides

When working on development branches or local forks, dependencies can be overridden using an `environment.user.yaml` file:

```yaml
dependencies:
  - pip:
      - 'git+file:///path/to/flepimop2'
      - 'git+file:///path/to/op_engine'
      - 'git+file:///path/to/op_engine#subdirectory=flepimop2-op_engine'
```

When running:

<!-- skip-test -->
```bash
just venv
```

this file will be merged with `environment.yaml`.

Alternatively, individual packages can be reinstalled inside the environment:

<!-- skip-test -->
```bash
pip install --force-reinstall file:///path/to/flepimop2
pip install --force-reinstall file:///path/to/op_engine
pip install --force-reinstall file:///path/to/op_engine#subdirectory=flepimop2-op_engine
```

This allows incremental iteration without recreating the full environment.

------------------------------------------------------------------------

## Handwritten SIR Model and Solver

This section demonstrates using `flepimop2` with fully user-defined components. The goal is to show how systems, solvers, and configuration are composed into a working simulation pipeline without relying on built-in modeling assumptions.

To begin using `flepimop2`, you will need three inputs:

1. A Python file defining the SIR model in terms of dY/dt, called a **system**
2. A Python file defining the ODE solver, called an **engine**
3. A YAML configuration file wiring everything together

------------------------------------------------------------------------

## SIR System Definition

Create `model_input/plugins/SIR.py`:

```python
import numpy as np
from numpy.typing import NDArray


def stepper(
    t: float,
    y: NDArray[np.float64],
    beta: float,
    gamma: float,
) -> NDArray[np.float64]:
    """dY/dt for the SIR model."""
    y_s, y_i, _ = np.asarray(y, dtype=float)
    infection = (beta * y_s * y_i) / np.sum(y)
    recovery = gamma * y_i
    dydt = [-infection, infection - recovery, recovery]
    return np.array(dydt, dtype=float)
```

This function defines the SIR model as a system of ordinary differential equations. The arguments are:

1. `t` — the current simulation time (unused here, but available for time-dependent effects)
2. `y` — the state vector containing compartment values
3. `beta` and `gamma` — model parameters provided by `flepimop2` from the configuration file

------------------------------------------------------------------------

## ODE Solver Definition

Create `model_input/plugins/solve_ivp.py`:

```python
from typing import Any

import numpy as np
from flepimop2.system.abc import SystemProtocol
from numpy.typing import NDArray
from scipy.integrate import solve_ivp


def runner(
    fun: SystemProtocol,
    times: NDArray[np.float64],
    y0: NDArray[np.float64],
    params: dict[str, Any] | None = None,
    **solver_options: Any,
) -> NDArray[np.float64]:
    if not (times.ndim == 1 and times.size >= 1):
        msg = "times must be a 1D sequence of time points"
        raise ValueError(msg)

    times.sort()

    t0, tf = 0.0, times[-1]
    if times[0] < t0:
        msg = f"times[0] must be >= 0; got times[0]={times[0]}"
        raise ValueError(msg)

    args = tuple(val for val in params.values()) if params is not None else None
    result = solve_ivp(fun, (t0, tf), y0, t_eval=times, args=args, **solver_options)
    return np.transpose(np.vstack((result.t, result.y)))
```

This defines an ODE solver that takes a generic `fun` stepper function and wraps `scipy.integrate.solve_ivp`. It also takes:

- `times`: an array defining time points to evaluate the solution
- `y0`: the initial state vector
- `params`: additional parameters passed to the stepper
- `solver_options`: solver-specific keyword arguments forwarded to SciPy

------------------------------------------------------------------------

## Configuration File

Create `configs/SIR_script.yml`:

```yaml
name: SIR_handwritten_model

system:
  - module: wrapper
    script: model_input/plugins/SIR.py

engine:
  - module: wrapper
    script: model_input/plugins/solve_ivp.py

simulate:
  demo:
    times: [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
  hires:
    times: 0.0:0.1:100.0

backend:
  - module: csv

parameter:
  beta:
    module: fixed
    value: 0.3
  gamma:
    module: fixed
    value: 0.1
  s0:
    module: fixed
    value: 999
  i0:
    module: fixed
    value: 1
  r0:
    module: fixed
    value: 0
```

This defines the configuration for a handwritten SIR model. It has the following important sections:

1. `name` which defines a human readable name for the configuration file.
2. `system` which defines the systems available. In this case we have a system that uses the `wrapper` module that loads the handwritten SIR stepper function from before.
3. `engine` which defines the engines available. In this case we have an engine that uses the `wrapper` module that loads the handwritten `solve_ivp` ODE solver function from before.
4. `simulate` which defines the available simulators, which are a combination of a system and an engine with settings. In this case we define two simulators, `demo` and `hires` which both use the same system and engine defined before but with different resolutions of time grids.
5. `backend` which defines the backend to use. In this case the backend is a `csv` module which will save results using plain CSV files.
6. `parameter` which defines the parameters used by the stepper and runner to run the simulator.

------------------------------------------------------------------------

## Running the Handwritten Simulation

```bash
flepimop2 simulate configs/SIR_script.yml
```

This will run the `demo` simulator since it is the first simulator defined in the configuration file. You can specify a different simulator using the `--target` option.

After completion, a CSV file will be created in `model_output/`.

------------------------------------------------------------------------

## Adding Postprocessing Pipelines

`flepimop2` supports postprocessing pipelines through its `process` command, allowing both R- and Python-based workflows to be orchestrated from configuration.

Add:

```yaml
process:
  demo:
    module: shell
    command: Rscript postprocessing/SIR_plot.R
    args:
      - configs/SIR_script.yml
      - model_output/SIR_plot.png
  hires:
    module: shell
    command: Rscript postprocessing/SIR_plot.R
    args:
      - configs/SIR_script.yml
      - model_output/SIR_plot_hires.png
  jupyter_render:
    module: ipynbrender
    file: postprocessing/SirPlot.ipynb
    output: model_output/SirPlot.html
```

------------------------------------------------------------------------

## Running Processing Steps

Plot results:

```bash
flepimop2 process configs/SIR_script.yml
```

Render notebook:

```bash
flepimop2 process --target jupyter_render configs/SIR_script.yml
```

Debug:

```bash
flepimop2 process --target jupyter_render --dry-run -vvv configs/SIR_script.yml
```

------------------------------------------------------------------------

## Using `op_engine` as the Solver Backend

The `op_engine` integration demonstrates how solver backends can be swapped without modifying the model definition.

Rather than redefining the SIR system, the op_engine configuration only changes the engine block and adds a Python-based postprocessing step.

### Engine Change

In `configs/SIR_op_engine.yml`, the engine definition becomes:

```yaml
engine:
  - module: op_engine
    config:
      method: heun
      adaptive: false
      strict: true
      rtol: 1.0e-6
      atol: 1.0e-9
```

------------------------------------------------------------------------

### Python-Based Postprocessing

The op_engine configuration adds:

```yaml
process:
  plot_demo:
    module: shell
    command: python postprocessing/SIR_plot_op_engine.py
    args:
      - configs/SIR_op_engine.yml
      - model_output/SIR_plot_op_engine.png
```

------------------------------------------------------------------------

## Running the op_engine Pipeline

Run simulation:

```bash
flepimop2 simulate configs/SIR_op_engine.yml
```

Generate plots:

```bash
flepimop2 process configs/SIR_op_engine.yml
```

------------------------------------------------------------------------

## Summary

This demo illustrates:

- Building systems and solvers manually
- Running simulations through `flepimop2`'s CLI
- Adding postprocessing pipelines
- Swapping solver backends without changing the model
- Integrating third-party solvers such as `op_engine`
- Coordinating Python and R workflows
- Building composable, configuration-driven simulation pipelines
