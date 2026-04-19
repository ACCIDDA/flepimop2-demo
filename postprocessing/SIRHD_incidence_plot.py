"""SIRHD 4-panel plot: prevalence + weekly incidence (cases, hosp, deaths).

Works for both the classic (flat) and vaccination-structured models.
When axes are present the raw states are aggregated before plotting.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from flepimop2.configuration import ConfigurationModel

ARG_LEN = 2
WEEK = 7
COMPARTMENTS = ("S", "I", "H", "R", "D")

_trapz = np.trapezoid


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _latest_csv(results_dir: Path, *, n_cols: int) -> Path:
    csvs = sorted(
        results_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not csvs:
        msg = f"No CSV files found in {results_dir}"
        raise FileNotFoundError(msg)
    for csv_path in csvs:
        with csv_path.open() as fh:
            first_line = fh.readline()
        if first_line.count(",") + 1 == n_cols:
            return csv_path
    msg = f"No CSV with {n_cols} columns in {results_dir}"
    raise FileNotFoundError(msg)


def _resolve_results_dir(config_model: ConfigurationModel) -> Path:
    first_sim = next(iter(config_model.simulate.values()))
    backend_name = getattr(first_sim, "backend", None) or "default"
    backend_model = config_model.backends.get(backend_name)
    if backend_model is None:
        msg = f"backend {backend_name!r} not found"
        raise KeyError(msg)
    cfg = backend_model.model_dump()
    root = (
        cfg.get("root")
        or cfg.get("config", {}).get("root")
        or cfg.get("params", {}).get("root")
        or cfg.get("settings", {}).get("root")
        or "model_output"
    )
    return Path(root)


def _get_param(config_model: ConfigurationModel, name: str) -> float:
    return float(config_model.parameters[name].value)


def _aggregate(df: pd.DataFrame, state_names: list[str]) -> pd.DataFrame:
    """Sum columns sharing the same base compartment (e.g. S__vax_u + S__vax_v → S)."""
    structured = any("__" in s for s in state_names)
    if not structured:
        return df  # already flat

    for comp in COMPARTMENTS:
        cols = [c for c in state_names if c == comp or c.startswith(f"{comp}__")]
        if cols:
            df[comp] = df[cols].sum(axis=1)
    return df


def _stratum_cols(state_names: list[str], comp: str) -> list[str]:
    """Return the per-stratum columns for *comp* (or [comp] if flat)."""
    cols = [c for c in state_names if c == comp or c.startswith(f"{comp}__")]
    return cols or [comp]


# ---------------------------------------------------------------------------
# incidence computation
# ---------------------------------------------------------------------------
def _compute_daily_incidence(
    df: pd.DataFrame,
    state_names: list[str],
    config_model: ConfigurationModel,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return (daily_cases, daily_hosp, daily_deaths) as pd.Series."""
    beta = _get_param(config_model, "beta")
    t_inf = _get_param(config_model, "t_inf")
    rho = _get_param(config_model, "rho")
    delta = _get_param(config_model, "delta")
    t_hosp = _get_param(config_model, "t_hosp")

    n_total = df["S"] + df["I"] + df["H"] + df["R"]
    lam = beta * df["I"] / n_total

    # Cases: flow S → I
    daily_cases = lam * df["S"]

    # Hospitalisation: flow I → H  (per-stratum rates if structured)
    i_cols = _stratum_cols(state_names, "I")
    daily_hosp = pd.Series(0.0, index=df.index)
    for col in i_cols:
        q = _effective_q(col, config_model)
        daily_hosp += (q * rho / t_inf) * df[col]

    # Deaths: flow H → D  (per-stratum rates if structured)
    h_cols = _stratum_cols(state_names, "H")
    daily_deaths = pd.Series(0.0, index=df.index)
    for col in h_cols:
        q = _effective_q(col, config_model)
        daily_deaths += (q * delta / t_hosp) * df[col]

    return daily_cases, daily_hosp, daily_deaths


def _effective_q(col: str, config_model: ConfigurationModel) -> float:
    """Return the q multiplier for a (possibly stratified) column.

    For flat models q=1.  For structured models look up q__<suffix>.
    """
    m = re.match(r"[A-Z](__.*)", col)
    if m is None:
        return 1.0
    suffix = m.group(1)  # e.g. "__vax_u"
    param_name = f"q{suffix}"
    return _get_param(config_model, param_name)


def _weekly_incidence(
    time: np.ndarray,
    daily: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Aggregate daily rates into weekly totals via trapezoidal integration."""
    n_weeks = int(np.floor(time[-1] / WEEK))
    week_mid = np.arange(n_weeks) * WEEK + WEEK / 2
    weekly = np.zeros(n_weeks)
    for w in range(n_weeks):
        mask = (time >= w * WEEK) & (time < (w + 1) * WEEK)
        weekly[w] = _trapz(daily[mask], time[mask])
    return week_mid, weekly


# ---------------------------------------------------------------------------
# plotting
# ---------------------------------------------------------------------------
def _compute_cumulative_vax(
    df: pd.DataFrame,
    state_names: list[str],
    config_model: ConfigurationModel,
    time: np.ndarray,
) -> np.ndarray | None:
    """Return cumulative vaccines administered, or *None* for non-vax models."""
    structured = any("__" in s for s in state_names)
    has_vax = structured and any(p in config_model.parameters for p in ("k", "nu"))
    if not has_vax:
        return None

    s_u_col = next(c for c in state_names if c.startswith("S__") and c.endswith("_u"))
    r_u_col = next(c for c in state_names if c.startswith("R__") and c.endswith("_u"))

    if "k" in config_model.parameters:
        k = _get_param(config_model, "k")
        cap_l = _get_param(config_model, "cap_l")
        t_s = _get_param(config_model, "t_s")
        ramp = _get_param(config_model, "ramp")
        n0 = _get_param(config_model, "n0")
        pop_vw = sum(
            df[c]
            for c in state_names
            if c.endswith(("_v", "_w")) and not c.startswith("D")
        )
        coverage = pop_vw / n0
        sigmoid = 1.0 / (1.0 + np.exp(-ramp * (time - t_s)))
        u_rate = np.maximum(0.0, k * (cap_l - coverage)) * sigmoid
        daily_vax = u_rate * (df[s_u_col] + df[r_u_col])
    else:
        nu = _get_param(config_model, "nu")
        daily_vax = nu * (df[s_u_col] + df[r_u_col])

    cum_vax = np.zeros(len(time))
    for i in range(1, len(time)):
        cum_vax[i] = cum_vax[i - 1] + 0.5 * (
            daily_vax.iloc[i - 1] + daily_vax.iloc[i]
        ) * (time[i] - time[i - 1])
    return cum_vax


def main() -> None:
    """CLI entry point: generate SIRHD incidence plot from config + CSV."""
    args = sys.argv[1:]
    if len(args) != ARG_LEN:
        msg = "Usage: SIRHD_incidence_plot.py <config.yml> <output.png>"
        raise SystemExit(msg)

    cfg_path, out_path = Path(args[0]), Path(args[1])
    config_model = ConfigurationModel.from_yaml(cfg_path)

    # --- load simulation CSV --------------------------------------------------
    first_sim = next(iter(config_model.simulate.values()))
    state_names = list(first_sim.initial_state.keys())
    n_cols = len(state_names) + 1

    results_dir = _resolve_results_dir(config_model)
    latest = _latest_csv(results_dir, n_cols=n_cols)
    df = pd.read_csv(latest, header=None)
    df.columns = ["time", *state_names]

    # --- aggregate strata → S, I, H, R, D ------------------------------------
    df = _aggregate(df, state_names)

    # --- incidence ------------------------------------------------------------
    daily_cases, daily_hosp, daily_deaths = _compute_daily_incidence(
        df, state_names, config_model
    )
    time = df["time"].to_numpy()
    wk_mid, wk_cases = _weekly_incidence(time, daily_cases.to_numpy())
    _, wk_hosp = _weekly_incidence(time, daily_hosp.to_numpy())
    _, wk_deaths = _weekly_incidence(time, daily_deaths.to_numpy())

    # --- subtitle hint --------------------------------------------------------
    structured = any("__" in s for s in state_names)
    agg_note = " (aggregated across strata)" if structured else ""

    # --- cumulative vaccinations (structured models only) ---------------------
    cum_vax = _compute_cumulative_vax(df, state_names, config_model, time)

    # --- figure ---------------------------------------------------------------
    _render_figure(
        config_model,
        df,
        time,
        agg_note,
        wk_mid,
        wk_cases,
        wk_hosp,
        wk_deaths,
        cum_vax,
        Path(out_path),
    )


def _render_figure(  # noqa: PLR0913
    config_model: ConfigurationModel,
    df: pd.DataFrame,
    time: np.ndarray,
    agg_note: str,
    wk_mid: np.ndarray,
    wk_cases: np.ndarray,
    wk_hosp: np.ndarray,
    wk_deaths: np.ndarray,
    cum_vax: np.ndarray | None,
    out_path: Path,
) -> None:
    """Build and save the multi-panel figure."""
    n_panels = 5 if cum_vax is not None else 4
    fig, axes = plt.subplots(n_panels, 1, figsize=(10, 3.5 * n_panels), sharex=True)

    colors = {"S": "C0", "I": "C1", "H": "C2", "R": "C3", "D": "C4"}

    ax = axes[0]
    for comp in COMPARTMENTS:
        ax.plot(df["time"], df[comp], label=comp, color=colors[comp], linewidth=1.2)
    ax.set_ylabel("Population")
    ax.set_title(f"{config_model.name} — Prevalence{agg_note}")
    ax.legend(loc="right")
    ax.grid(alpha=0.3)

    for ax, data, ylabel, title, color in [
        (axes[1], wk_cases, "Weekly cases", "Weekly Incident Cases", "C1"),
        (
            axes[2],
            wk_hosp,
            "Weekly hospitalisations",
            "Weekly Incident Hospitalisations",
            "C2",
        ),
        (axes[3], wk_deaths, "Weekly deaths", "Weekly Incident Deaths", "C4"),
    ]:
        ax.bar(wk_mid, data, width=WEEK * 0.8, color=color, alpha=0.8)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(alpha=0.3)

    if cum_vax is not None:
        ax = axes[4]
        ax.plot(time, cum_vax, color="C5", linewidth=1.4)
        ax.set_ylabel("Cumulative doses")
        ax.set_title("Cumulative Vaccines Administered")
        ax.grid(alpha=0.3)

    axes[-1].set_xlabel("Time (days)")

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    sys.stdout.write(f"Plot saved to {out_path}\n")


if __name__ == "__main__":
    main()
