# `flepimop2` Demo

Contained in this repository is a demonstration guiding new users through the capabilities of `flepimop2` starting from a basic SIR model and building up from there.

## Installation

To create a conda virtual environment containing `flepimop2` and the other dependencies you can run the following recipe which will create a conda environment locally at `./venv/`. This will generate the conda environment from `environment.yaml`.

```bash
$ just venv
$ conda activate ./venv
```

### Development Installation

For users that wish to change from where `flepimop2` is installed from they can create a `environment.user.yaml` file with their modifications:.

```yaml
dependencies:
  - pip:
      - 'git+file:///path/to/flepimop2'
```

Then when running `just venv` this file will be used to override the `environment.yaml` when generating the conda environment. Alternatively, to override the installation of `flepimop2` when actively working inside the conda environment users can run the following:

```bash
pip install --force-reinstall file:///path/to/flepimop2
```

This allows for incremental updates without recreating or updating the conda environment as a whole. Similar steps apply to other dependencies as well.

## Hand Rolling an SIR Model and ODE Solver

### Model Inputs

To begin using `flepimop2` you'll need to create 3 files:

1. A python file defining the SIR model in terms of $dY/dt$, which `flepimop2` calls a "system".
2. A python file defining the ODE solver to be used, which `flepimop2` calls an "engine".
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

1. `t` which is the current time step, which is unused in this model but could be used to add time dependent effects.
2. `y` which is the state array which defines the number of individuals in each compartment.
3. `beta` and `gamma` which are additional parameter arguments that are provided by `flepimop2` from the configuration.

#### ODE Solver

To create an ODE solver you'll want to put the following code in a file called `model_input/plugins/solve_ivp.py`.

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

This defines an ODE solver that takes a generic `fun` stepper function and wraps `scipy.integrate.solve_ivp`. It also takes a `times` array defining the time steps to evaluate at, a `y0` initial state array, `params` are additional params to pass on to the stepper, and `solver_options` are solver specific options.

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

This defines the configuration for a handwritten SIR model. It has the following important sections:

1. `name` which defines a human readable name for the configuration file.
2. `system` which defines the systems available. In this case we have a system that uses the `wrapper` module that loads the handwritten SIR stepper function from before.
3. `engine` which defines the engines available. In this case we have an engine that uses the `wrapper` module that loads the handwritten `solve_ivp` ODE solver function from before.
4. `simulate` which defines the available simulators, which are a combination of a system and an engine with settings. In this case we define to simulators, `demo` and `hires` which both use the same system and engine defined before but with different resolutions of time grids.
5. `backend` which defines the backend to use. In this case the backend is a `csv` module which will save results using plain CSV files.
6. `parameter` which defines the parameters used by the stepper and runner to run the simulator.

### Running Simulate

Now you are able to run simulators with `flepimop2` using the CLI. The command to do so is:

```bash
flepimop2 simulate configs/SIR_script.yml
```

This will run the `demo` simulator since it is the first simulator defined in the configuration file. You can specify which one to run by providing a `--target` option. After this command completes you should see a CSV file created in the `model_output/` directory.

### Running Processing Steps

#### Updating The Configuration

Now you'll want to add the following section to your configuration file.

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

This will define three processing steps that use two modules. `demo` and `hires` invoke a shell command with a set of user provided arguments and `jupyter_render` renders a jupyter notebook.

#### Running a Shell Script

You can invoke the plotting processing script via the following command.

```bash
flepimop2 process configs/SIR_script.yml
```

This will produce a png plot file in the `model_output/` directory.

#### Running a Jupyter Notebook

The `jupyter_render` process target uses a process module not directly provided by `flepimop2`, it is provided by [`flepimop2-ipynbrender`](https://github.com/ACCIDDA/flepimop2-ipynbrender) which is an external package. This external package provides additional debugging features available via the `--dry-run` and `--verbose` flags. To see the additional debug information you can run the following command.

```bash
flepimop2 process --target jupyter_render --dry-run -vvv configs/SIR_script.yml
```

Once you are satisfied with the output you can invoke the command with the debug flags to actually run it.

```bash
flepimop2 process --target jupyter_render configs/SIR_script.yml
```
