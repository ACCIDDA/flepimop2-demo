import numpy as np

def stepper(t: float, y: np.ndarray, beta: float, gamma: float) -> np.ndarray:
    """
    dYdt for the SIR model.
    """
    S, I, R = np.asarray(y, dtype=float)
    N = S + I + R
    infection = beta * S * I / N
    recovery = gamma * I
    dS = -infection
    dI = infection - recovery
    dR = recovery
    return np.array([dS, dI, dR], dtype=float)
