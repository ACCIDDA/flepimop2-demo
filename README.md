# `flepimop2` Demo

Contained in this repository is a demonstration guiding new users through the capabilities of `flepimop2` starting from a basic SIR model and building up from there.

# Installation

To create a conda virtual environment containing `flepimop2` and the other dependencies you can run the following recipe which will create a conda environment locally at `./venv/`. This will generate the conda environment from `environment.yaml`.

```bash
$ just venv
$ conda activate ./venv
```

## Development Installation

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

# The SIR model and an ODE solver

Let's start with a basic task: simulating the SIR model system. If you have coded the SIR model previously, that implementation probably looked like:

```python
def stepper(t, y, beta, gamma):
    y_S, y_I, y_R = y
    infection = beta * y_S * y_I / np.sum(y)
    recovery = gamma * y_I
    dYdt = [-infection, infection - recovery, recovery]  # noqa: N806
    return dYdt
```

and you might have used an ODE solver like [scipy's solve_ivp]() to generate a time series:

```python
# ... set elsewhere the variables like t0, tf, etc
result = solve_ivp(stepper, (t0, tf), y0, t_eval=times, args=(beta, gamma))
```

`flepimop` supports using hand-written code, which you can see with:

```bash
flepimop2 simulate configs/SIR_script.yml
```

This command deposits data in `model_output`. The relevant configuration sections are `system` (i.e. the model dynamics) and `engine` (i.e. the solver).

You can then post-process the results with a plotting script:

```bash
flepimop2 process configs/SIR_script.yml
```
