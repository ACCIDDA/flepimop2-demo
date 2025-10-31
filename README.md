# `flepimop2` Demo

Contained in this repository is a demonstration guiding new users through the capabilities of `flepimop2` starting from a basic SIR model and building up from there.

# Development Mode

If you're using the demo repository alongside a developer copy of the library, for example to work on demonstrating a new feature, you can incrementally update `flepimop2` by invoking:

```bash
(flepimop2-demo/venv) flepimop2-demo$ pip install --force-reinstall file:///${FLEPI_PATH}/flepimop2
```

# Installation

TODO. Temporarily:

```bash
$ just venv
$ conda activate ./venv
```

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
flepimop2-demo$ flepimop2 simulate configs/SIR_script.yml
```

... which deposits data in `model_output`. The relevant configuration sections are `system` (i.e. the model dynamics) and `engine` (i.e. the solver).

You can then post-process the results with a plotting script:

```bash
flepimop2-demo$ flepimop2 process configs/SIR_script.yml
```

