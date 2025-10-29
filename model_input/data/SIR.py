# noqa: INP001, D100
import numpy as np


def stepper(_t: float, y: np.ndarray, beta: float, gamma: float) -> np.ndarray:
    """Dydt for the SIR model."""
    y_S, y_I, _ = np.asarray(y, dtype=float)  # noqa: N806
    infection = beta * y_S * y_I / np.sum(y)
    recovery = gamma * y_I
    dYdt = [-infection, infection - recovery, recovery]  # noqa: N806
    return np.array(dYdt, dtype=float)
