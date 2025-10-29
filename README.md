# `flepimop2` Demo

Contained in this repository is a demonstration guiding new users through the capabilities of `flepimop2` starting from a basic SIR model and building up from there.

# Development Mode

If you're using the demo repository alongside a developer copy of the library, for example to work on demonstrating a new feature, you can incrementally update `flepimop2` by invoking:

```bash
(flepimop2-demo/venv) flepimop2-demo$ pip install --force-reinstall file:///home/holism/workspaces/flepimop2
```

# Installation

TODO. Temporarily:

```bash
$ just venv
$ conda activate ./venv
```

# The SIR model and an ODE solver

Let's start with a basic task: simulating the SIR model system.

```bash
$ flepimop2 simulate configs/built/SIR_script.yml
```