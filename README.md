# `flepimop2` Demo

This repository contains a demonstration project designed to introduce users to the `flepimop2` simulation framework. The demo starts from a fully handwritten SIR model and solver, then progresses to using the `op_engine` integration to run simulations through the same `flepimop2` engine interface.

The goal is to illustrate:

- How to define systems and solvers manually
- How to configure and run simulations
- How to add postprocessing steps
- How to swap solver backends (handwritten → `op_engine`) without changing the model definition

---

## Installation

To create a conda environment containing `flepimop2`, `op_engine`, the `flepimop2-op-engine` adapter, and all demo dependencies, run:

```bash
just venv
conda activate ./venv
```

This creates a local environment under `./venv/` using `environment.yaml`.

---

## Development Installation Overrides

If you want to override where `flepimop2`, `op_engine`, or the `flepimop2-op-engine` adapter are installed from, create an `environment.user.yaml` file, for example point at an alternative branch:

```yaml
dependencies:
  - pip:
      - 'git+file:///path/to/flepimop2'
      - 'git+file:///path/to/op_engine'
      - 'git+file:///path/to/op_engine#subdirectory=flepimop2-op_engine'
```

When running:

```bash
just venv
```

this file will be merged with `environment.yaml` and override the base pip dependencies.

Alternatively, when actively developing inside the environment, you can reinstall individual packages without rebuilding the environment:

```bash
pip install --force-reinstall file:///path/to/flepimop2
pip install --force-reinstall file:///path/to/op_engine
pip install --force-reinstall file:///path/to/op_engine#subdirectory=flepimop2-op_engine
```

---

# Part 1 — Handwritten SIR Model and Solver

This section demonstrates using `flepimop2` with fully user-defined components.

---

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

---

## Running the Handwritten Simulation

```bash
flepimop2 simulate configs/SIR_script.yml
```

---

# Part 3 — Using `op_engine` as the Solver Backend

Run:

```bash
flepimop2 simulate configs/SIR_op_engine.yml
```

---

# Part 4 — Postprocessing op_engine Results

```bash
flepimop2 process configs/SIR_op_engine.yml
```

---

## Summary

This demo illustrates:

- Building systems and solvers manually
- Running simulations through flepimop2’s CLI
- Adding postprocessing pipelines
- Swapping solver backends without changing the model
- Integrating third-party solvers such as `op_engine` through adapter packages