"""Generate heatmap of scenario sweep outcomes for vaccination campaign parameters.

Reads scenario_*.csv files from model_output and creates a heatmap showing
total hospitalizations relative to the configured default policy
(parameter block: r0, cap_l) across transmission intensity and
vaccine coverage caps.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from flepimop2.configuration import ConfigurationModel
from matplotlib.patches import Rectangle

ARG_LEN = 2


@dataclass(frozen=True)
class HeatmapMeta:
    """Metadata needed to render and save the heatmap."""

    r0_vals: list[float]
    cap_l_vals: list[float]
    default_x: int
    default_y: int
    default_r0: float
    default_cap_l: float
    out_path: Path


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


def _get_scenario_params(cfg: dict[str, Any]) -> dict[str, list]:
    """Extract first scenario parameter grid from raw YAML config."""
    scenarios = cfg.get("scenarios")
    if not isinstance(scenarios, dict) or not scenarios:
        msg = "No scenarios defined in config"
        raise ValueError(msg)

    scenario = next(iter(scenarios.values()))
    if not isinstance(scenario, dict):
        msg = "Scenario definition must be a mapping"
        raise TypeError(msg)
    params = scenario.get("parameters")
    if not isinstance(params, dict):
        msg = "Scenario parameters must be a mapping"
        raise TypeError(msg)
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
    time = df.iloc[:, 0].to_numpy()  # First column is time

    # Trapezoidal integration for total cumulative hospitalizations
    total_hosp = np.trapezoid(h_totals.to_numpy(), time)
    return float(total_hosp)


def _find_value_index(
    values: list[float], target: float, tol: float = 1e-9
) -> int | None:
    """Find index of target value in a numeric list with tolerance."""
    for i, v in enumerate(values):
        if abs(float(v) - target) <= tol:
            return i
    return None


def _resolve_results_dir(config_model: ConfigurationModel) -> Path:
    """Resolve CSV backend output root from config."""
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
    return Path(root)


def _compute_outcomes(
    csv_files: list[Path],
    r0_vals: list[float],
    cap_l_vals: list[float],
) -> np.ndarray:
    """Compute matrix of integrated hospitalization burden outcomes."""
    h_col_indices = [7, 8, 9]
    outcomes = np.zeros((len(cap_l_vals), len(r0_vals)))

    for scenario_idx, csv_file in enumerate(csv_files):
        df = pd.read_csv(csv_file, header=None)
        total_hosp = _compute_total_hospitalizations(df, h_col_indices)

        # product(r0, cap_l): cap_l is the fast axis.
        t_start_idx = scenario_idx // len(cap_l_vals)
        cap_l_idx = scenario_idx % len(cap_l_vals)
        outcomes[cap_l_idx, t_start_idx] = total_hosp

    return outcomes


def _plot_heatmap(
    pct_change: np.ndarray,
    meta: HeatmapMeta,
) -> None:
    """Render and save annotated percent-change heatmap."""
    abs_max = float(np.abs(pct_change).max())
    vmax = float(np.ceil(abs_max))
    vmin = -vmax

    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(
        pct_change,
        cmap="RdYlGn_r",
        aspect="auto",
        origin="lower",
        vmin=vmin,
        vmax=vmax,
    )

    ax.set_xticks(range(len(meta.r0_vals)))
    ax.set_xticklabels(meta.r0_vals)
    ax.set_yticks(range(len(meta.cap_l_vals)))
    ax.set_yticklabels(meta.cap_l_vals)

    ax.add_patch(
        Rectangle(
            (meta.default_x - 0.5, meta.default_y - 0.5),
            1.0,
            1.0,
            fill=False,
            edgecolor="black",
            linewidth=2.5,
        ),
    )

    ax.set_xlabel("Basic Reproduction Number (R0)", fontsize=12, fontweight="bold")
    ax.set_ylabel("Vaccine Coverage Cap", fontsize=12, fontweight="bold")
    title = (
        "Total Hospitalizations vs. Baseline\n"
        f"(r0={meta.default_r0:g}, cap_l={meta.default_cap_l:g})"
    )
    ax.set_title(title, fontsize=13, fontweight="bold")

    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("% Change from Baseline", fontsize=11, fontweight="bold")

    for i in range(len(meta.cap_l_vals)):
        for j in range(len(meta.r0_vals)):
            if i == meta.default_y and j == meta.default_x:
                continue
            val = float(pct_change[i, j])
            text_color = "black" if abs(val) < abs_max * 0.25 else "white"
            rounded_pct = round(val)
            ax.text(
                j,
                i,
                f"{rounded_pct:+d}%",
                ha="center",
                va="center",
                color=text_color,
                fontsize=10,
                fontweight="bold",
            )

    fig.tight_layout()
    meta.out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(meta.out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    sys.stdout.write(f"Heatmap saved to {meta.out_path}\n")


def _default_coords(
    config_model: ConfigurationModel,
    r0_vals: list[float],
    cap_l_vals: list[float],
) -> tuple[float, float, int, int]:
    """Return default r0/cap_l values and their grid indices."""
    default_r0 = float(config_model.parameters["r0"].value)
    default_cap_l = float(config_model.parameters["cap_l"].value)
    default_x = _find_value_index([float(v) for v in r0_vals], default_r0)
    default_y = _find_value_index([float(v) for v in cap_l_vals], default_cap_l)
    if default_x is None or default_y is None:
        msg = "Configured default r0/cap_l is not on the scenario grid"
        raise ValueError(msg)
    return default_r0, default_cap_l, default_x, default_y


def main() -> None:
    """CLI entry point: generate scenario heatmap from config + CSVs."""
    args = sys.argv[1:]
    if len(args) != ARG_LEN:
        msg = "python postprocessing/scenario_heatmap.py <config.yml> <output.png>"
        raise SystemExit(msg)

    cfg_path = Path(args[0])
    out_path = Path(args[1])

    with cfg_path.open() as f:
        raw_cfg = yaml.safe_load(f)

    config_model = ConfigurationModel.from_yaml(cfg_path)
    results_dir = _resolve_results_dir(config_model)

    # Get scenario parameters from config
    scenario_params = _get_scenario_params(raw_cfg)
    r0_vals = scenario_params["r0"]
    cap_l_vals = scenario_params["cap_l"]

    # Read all scenario CSV files
    csv_files = _latest_csv(results_dir, "scenario_*.csv")
    if not csv_files:
        msg = f"No scenario_*.csv files found in {results_dir}"
        raise FileNotFoundError(msg)

    outcomes = _compute_outcomes(
        csv_files,
        [float(v) for v in r0_vals],
        [float(v) for v in cap_l_vals],
    )
    default_r0, default_cap_l, default_x, default_y = _default_coords(
        config_model,
        [float(v) for v in r0_vals],
        [float(v) for v in cap_l_vals],
    )
    baseline = outcomes[default_y, default_x]
    pct_change = (outcomes / baseline - 1.0) * 100.0 if baseline > 0 else outcomes
    heatmap_meta = HeatmapMeta(
        [float(v) for v in r0_vals],
        [float(v) for v in cap_l_vals],
        default_x,
        default_y,
        default_r0,
        default_cap_l,
        out_path,
    )
    _plot_heatmap(pct_change, heatmap_meta)


if __name__ == "__main__":
    main()
