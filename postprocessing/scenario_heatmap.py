"""Generate heatmap of scenario sweep outcomes for vaccination campaign parameters.

Reads scenario_*.csv files from model_output and creates a heatmap showing
total hospitalizations relative to the configured default policy
(parameter block: t_start, cap_l) across campaign start times and
vaccine coverage caps.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from flepimop2.configuration import ConfigurationModel
from matplotlib.patches import Rectangle

ARG_LEN = 2


def _latest_csv(results_dir: Path, pattern: str) -> list[Path]:
    """Get one CSV per scenario index (the most recent run), sorted numerically."""
    by_index: dict[int, Path] = {}
    for f in results_dir.glob(pattern):
        m = re.search(r"scenario_(\d+)", f.name)
        if m:
            idx = int(m.group(1))
            if idx not in by_index or f.name > by_index[idx].name:
                by_index[idx] = f
    return [by_index[i] for i in sorted(by_index)]


def _get_scenario_params(config_model: ConfigurationModel) -> dict[str, list]:
    """Extract scenario parameter grid from config."""
    scenarios = config_model.scenarios
    if not scenarios:
        msg = "No scenarios defined in config"
        raise ValueError(msg)

    # Get the first scenario (scenarios are keyed by name)
    scenario = next(iter(scenarios.values()))
    params = scenario.parameters

    return params


def _compute_total_hospitalizations(
    df: pd.DataFrame,
    h_col_indices: list[int],
) -> float:
    """Compute total cumulative hospitalizations from DataFrame.

    Args:
        df: DataFrame with columns [time, state0, state1, ...]
        h_col_indices: List of column indices for H (hospitalization) states

    """
    # Sum across all H strata at each time, then integrate
    h_totals = df.iloc[:, h_col_indices].sum(axis=1)
    time = df.iloc[:, 0].values  # First column is time

    # Trapezoidal integration for total cumulative hospitalizations
    total_hosp = np.trapezoid(h_totals.values, time)
    return float(total_hosp)


def _find_value_index(
    values: list[float], target: float, tol: float = 1e-9
) -> int | None:
    """Find index of target value in a numeric list with tolerance."""
    for i, v in enumerate(values):
        if abs(float(v) - target) <= tol:
            return i
    return None


def main() -> None:
    """CLI entry point: generate scenario heatmap from config + CSVs."""
    args = sys.argv[1:]
    if len(args) != ARG_LEN:
        msg = "python postprocessing/scenario_heatmap.py <config.yml> <output.png>"
        raise SystemExit(msg)

    cfg_path = Path(args[0])
    out_path = Path(args[1])

    config_model = ConfigurationModel.from_yaml(cfg_path)

    # Resolve results directory (same logic as SIRHD_incidence_plot.py)
    simulate_block = config_model.simulate
    first_sim = next(iter(simulate_block.values()))
    backend_name = getattr(first_sim, "backend", None) or "default"
    backend_model = config_model.backends.get(backend_name)

    if backend_model is None:
        msg = f"simulate backend {backend_name!r} not found in config.backends"
        raise KeyError(msg)

    backend_cfg = backend_model.model_dump()
    root = (
        backend_cfg.get("root")
        or backend_cfg.get("config", {}).get("root")
        or backend_cfg.get("params", {}).get("root")
        or "model_output"
    )
    results_dir = Path(root)

    # Get scenario parameters from config
    scenario_params = _get_scenario_params(config_model)
    t_start_vals = scenario_params["t_start"]
    cap_l_vals = scenario_params["cap_l"]

    # Read all scenario CSV files
    csv_files = _latest_csv(results_dir, "scenario_*.csv")
    if not csv_files:
        msg = f"No scenario_*.csv files found in {results_dir}"
        raise FileNotFoundError(msg)

    # For SIRHD[vax] model: cols are [time, S*3, I*3, H*3, R*3, D]
    # H columns are at indices 7, 8, 9
    h_col_indices = [7, 8, 9]

    # Process each scenario file and compute total hospitalizations
    outcomes = np.zeros((len(cap_l_vals), len(t_start_vals)))

    for scenario_idx, csv_file in enumerate(csv_files):
        df = pd.read_csv(csv_file, header=None)

        # Compute total hospitalizations
        total_hosp = _compute_total_hospitalizations(df, h_col_indices)

        # Map scenario index to grid position.
        # itertools.product(t_start_vals, cap_l_vals) iterates cap_l fastest:
        # scenario_0: (t_start[0], cap_l[0])
        # scenario_1: (t_start[0], cap_l[1])
        # scenario_2: (t_start[0], cap_l[2])
        # scenario_3: (t_start[1], cap_l[0]) ...
        t_start_idx = scenario_idx // len(cap_l_vals)
        cap_l_idx = scenario_idx % len(cap_l_vals)

        outcomes[cap_l_idx, t_start_idx] = total_hosp

    # Use configured default policy as the baseline for percent change.
    default_t_start = float(config_model.parameters["t_start"].value)
    default_cap_l = float(config_model.parameters["cap_l"].value)
    default_x = _find_value_index([float(v) for v in t_start_vals], default_t_start)
    default_y = _find_value_index([float(v) for v in cap_l_vals], default_cap_l)
    if default_x is None or default_y is None:
        msg = "Configured default t_start/cap_l is not on the scenario grid"
        raise ValueError(msg)

    baseline = outcomes[default_y, default_x]
    pct_change = (outcomes / baseline - 1.0) * 100.0 if baseline > 0 else outcomes

    # Symmetric colormap limits centred at 0
    abs_max = np.abs(pct_change).max()
    vmax = float(np.ceil(abs_max))
    vmin = -vmax

    # Create heatmap
    fig, ax = plt.subplots(figsize=(10, 6))

    im = ax.imshow(
        pct_change,
        cmap="RdYlGn_r",  # Red = increase (bad), Green = decrease (good)
        aspect="auto",
        origin="lower",
        vmin=vmin,
        vmax=vmax,
    )

    # Set axis labels and ticks
    ax.set_xticks(range(len(t_start_vals)))
    ax.set_xticklabels(t_start_vals)
    ax.set_yticks(range(len(cap_l_vals)))
    ax.set_yticklabels(cap_l_vals)

    # Highlight the configured default scenario cell.
    ax.add_patch(
        Rectangle(
            (default_x - 0.5, default_y - 0.5),
            1.0,
            1.0,
            fill=False,
            edgecolor="black",
            linewidth=2.5,
        ),
    )

    ax.set_xlabel("Campaign Start Time (days)", fontsize=12, fontweight="bold")
    ax.set_ylabel("Vaccine Coverage Cap", fontsize=12, fontweight="bold")
    ax.set_title(
        f"Total Hospitalizations vs. Baseline\n(t_start={default_t_start:g}, cap_l={default_cap_l:g})",
        fontsize=13,
        fontweight="bold",
    )

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label("% Change from Baseline", fontsize=11, fontweight="bold")

    # Add text annotations with % change values
    for i in range(len(cap_l_vals)):
        for j in range(len(t_start_vals)):
            val = pct_change[i, j]
            label = f"{val:+.1f}%"
            # Use white text except near the neutral centre where contrast is low
            text_color = "black" if abs(val) < abs_max * 0.25 else "white"
            ax.text(
                j,
                i,
                label,
                ha="center",
                va="center",
                color=text_color,
                fontsize=10,
                fontweight="bold",
            )

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Heatmap saved to {out_path}")
    plt.close()


if __name__ == "__main__":
    main()
