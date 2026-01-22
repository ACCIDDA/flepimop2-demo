# `flepimop2` Demo

Contained in this repository is a demonstration guiding new users through the capabilities of `flepimop2` starting from a basic SIR model and building up from there. In addition to a handwritten solver example, this demo also includes an example using the `op_engine` integration for running simulations through the `flepimop2` engine interface.

## Installation

To create a conda virtual environment containing `flepimop2`, `op_engine`, and the other dependencies you can run the following recipe which will create a conda environment locally at `./venv/`. This will generate the conda environment from `environment.yaml`.

```bash
$ just venv
$ conda activate ./venv
```

### Development Installation

For users that wish to change from where `flepimop2` or `op_engine` are installed from they can create an `environment.user.yaml` file with their modifications:

```yaml
dependencies:
  - pip:
      - 'git+file:///path/to/flepimop2'
      - 'git+file:///path/to/op_engine'
```

Then when running `just venv` this file will be used to override the `environment.yaml` when generating the conda environment. Alternatively, to override the installation of either package when actively working inside the conda environment users can run the following:

```bash
pip install --force-reinstall file:///path/to/flepimop2
pip install --force-reinstall file:///path/to/op_engine
```

This allows for incremental updates without recreating or updating the conda environment as a whole. Similar steps apply to other dependencies as well.

## Hand Rolling an SIR Model and ODE Solver

### Model Inputs

To begin using `flepimop2` with a handwritten solver you'll need to create three files:

1. A Python file defining the SIR model in terms of $dY/dt$, which `flepimop2` calls a "system".
2. A Python file defining the ODE solver to be used, which `flepimop2` calls an "engine".
3. A YAML file defining the configuration for the project.

#### SIR Model

To create an SIR model you'll want to put the following code into a file called `model_input/plugins/SIR.py`.

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

This defines the SIR model in terms of an ODE. The function takes the following arguments:

1. `t` which is the current time step.
2. `y` which is the state array defining the number of individuals in each compartment.
3. `beta` and `gamma` which are additional parameter arguments provided by `flepimop2` from the configuration.

#### ODE Solver

To create a handwritten ODE solver you'll want to put the following code in a file called `model_input/plugins/solve_ivp.py`.

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

#### Configuration File

Finally, the last input needed is a configuration file. You'll want to put the following configuration in a file called `configs/SIR_script.yml`.

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

### Running Simulate

You can run the handwritten solver example with:

```bash
flepimop2 simulate configs/SIR_script.yml
```

This will produce CSV output files in the `model_output/` directory.

## Using `op_engine` as the flepimop2 Engine

This repository also includes an example configuration that uses the `op_engine` flepimop2-compatible engine adapter instead of a handwritten solver. This demonstrates how `flepimop2` can delegate time integration to `op_engine` while keeping the same system definition and workflow.

### op_engine Configuration

The op_engine example configuration is provided in `configs/SIR_op_engine.yml`. It reuses the same SIR system definition but switches the engine to the built-in `op_engine` adapter.

At a high level, the differences are:

- The `engine` section references the `op_engine.flepimop2.engine` module.
- Solver options are provided through the op_engine configuration schema.
- No custom Python solver script is required.

### Running the op_engine Example

To run the SIR model using `op_engine` as the backend solver:

```bash
flepimop2 simulate configs/SIR_op_engine.yml
```

This will again write CSV output files into `model_output/`, using the same backend configuration and naming conventions.

## Postprocessing with Python

In addition to the existing R-based plotting example, this repository includes a Python-based postprocessing script for visualizing op_engine simulation results. This provides a lightweight, fully Python-native workflow using `pandas` and `matplotlib`.

You can run the Python plotting step via the process CLI target defined in the op_engine configuration file:

```bash
flepimop2 process configs/SIR_op_engine.yml
```

This will generate a PNG plot in the `model_output/` directory showing the SIR trajectories.

## Running Processing Steps (R and Jupyter)

The original R and Jupyter-based postprocessing examples remain unchanged and can still be used with the handwritten solver configuration.

### Running a Shell Script

```bash
flepimop2 process configs/SIR_script.yml
```

### Running a Jupyter Notebook

```bash
flepimop2 process --target jupyter_render --dry-run -vvv configs/SIR_script.yml
```

Once verified:

```bash
flepimop2 process --target jupyter_render configs/SIR_script.yml
```
