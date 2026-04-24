"""Run coarse R0/S0 sweeps and generate a 3x3 panel of heatmaps.

Rows: susceptible share at t=0 (S0 fraction): 30%, 50%, 70%
Cols: basic reproduction number R0: 1.1, 2.0, 4.0

Each panel is a t_start x cap_l heatmap (% change from panel default policy),
with a box around the default policy cell.
"""

from __future__ import annotations

import copy
import math
import re
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from flepimop2.configuration import ConfigurationModel
from matplotlib.patches import Rectangle

ARG_LEN_MIN = 2
SWEEP_SCENARIO_NAME = "vax_campaign"
PANEL_SCENARIO_NAME = "panel_grid"


def _latest_csv_by_index(
    results_dir: Path, pattern: str = "scenario_*.csv"
) -> list[Path]:
    """Get one CSV per scenario index (latest file by name), sorted numerically."""
    by_index: dict[int, Path] = {}
    for f in results_dir.glob(pattern):
        m = re.search(r"scenario_(\d+)", f.name)
        if not m:
            continue
        idx = int(m.group(1))
        if idx not in by_index or f.name > by_index[idx].name:
            by_index[idx] = f
    return [by_index[i] for i in sorted(by_index)]


def _compute_total_hospitalizations(
    df: pd.DataFrame, h_col_indices: list[int]
) -> float:
    """Compute H bed-days by integrating total H prevalence over time."""
    h_totals = df.iloc[:, h_col_indices].sum(axis=1)
    time = df.iloc[:, 0].values
    return float(np.trapezoid(h_totals.values, time))


def _find_value_index(
    values: list[float], target: float, tol: float = 1e-9
) -> int | None:
    for i, v in enumerate(values):
        if abs(float(v) - target) <= tol:
            return i
    return None


def _slug_float(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".").replace(".", "p")


def _set_param(cfg: dict, name: str, value: float) -> None:
    params = cfg.setdefault("parameter", {})
    if name not in params:
        raise KeyError(f"Missing parameter '{name}' in config")
    params[name]["value"] = float(value)


def _set_backend_root(cfg: dict, root: str) -> None:
    backend = cfg.get("backend", [])
    if not backend:
        raise ValueError("Config has no backend section")
    if not isinstance(backend, list):
        raise TypeError("backend section must be a list")
    backend[0]["root"] = root


def _scenario_param_values(
    config_model: ConfigurationModel,
    scenario_name: str,
    param_name: str,
) -> list[float]:
    """Read scenario parameter values from config and coerce to float list."""
    scenarios = config_model.scenarios
    if scenario_name not in scenarios:
        raise KeyError(f"Scenario {scenario_name!r} not found in config.scenarios")
    params = scenarios[scenario_name].parameters
    if param_name not in params:
        raise KeyError(
            f"Parameter {param_name!r} not found in scenarios[{scenario_name!r}]",
        )
    return [float(v) for v in params[param_name]]


def _extract_panel_matrix(
    results_dir: Path,
    t_start_vals: list[float],
    cap_l_vals: list[float],
    default_t_start: float,
    default_cap_l: float,
) -> np.ndarray:
    """Build panel matrix as % change from panel default policy."""
    csv_files = _latest_csv_by_index(results_dir)
    expected = len(t_start_vals) * len(cap_l_vals)
    if len(csv_files) != expected:
        msg = (
            f"Expected {expected} scenario files in {results_dir}, found {len(csv_files)}. "
            "Check that scenario_sweep completed for this panel."
        )
        raise ValueError(msg)

    h_col_indices = [7, 8, 9]
    outcomes = np.zeros((len(cap_l_vals), len(t_start_vals)))

    for scenario_idx, csv_file in enumerate(csv_files):
        df = pd.read_csv(csv_file, header=None)
        total_hosp = _compute_total_hospitalizations(df, h_col_indices)

        # product(t_start, cap_l): cap_l is the fast axis.
        t_start_idx = scenario_idx // len(cap_l_vals)
        cap_l_idx = scenario_idx % len(cap_l_vals)
        outcomes[cap_l_idx, t_start_idx] = total_hosp

    default_x = _find_value_index([float(v) for v in t_start_vals], default_t_start)
    default_y = _find_value_index([float(v) for v in cap_l_vals], default_cap_l)
    if default_x is None or default_y is None:
        raise ValueError("Default t_start/cap_l is not on scenario grid")

    baseline = outcomes[default_y, default_x]
    if baseline <= 0:
        raise ValueError(f"Non-positive panel baseline in {results_dir}: {baseline}")

    return (outcomes / baseline - 1.0) * 100.0


def _run_panel_simulation(
    base_cfg: dict,
    cfg_path: Path,
    out_dir: Path,
    r0_value: float,
    s_frac: float,
) -> None:
    """Run one 99-scenario panel into an isolated output directory."""
    cfg = copy.deepcopy(base_cfg)

    n0 = float(cfg["parameter"]["n0"]["value"])
    i0_total = sum(
        float(v["value"])
        for k, v in cfg["parameter"].items()
        if k.startswith("i0__vax_")
    )
    h0_total = sum(
        float(v["value"])
        for k, v in cfg["parameter"].items()
        if k.startswith("h0__vax_")
    )
    s0_non_u = sum(
        float(v["value"])
        for k, v in cfg["parameter"].items()
        if k.startswith("s0__vax_") and k != "s0__vax_u"
    )
    r0_non_u = sum(
        float(v["value"])
        for k, v in cfg["parameter"].items()
        if k.startswith("r0__vax_") and k != "r0__vax_u"
    )

    s0 = s_frac * n0 - s0_non_u
    if s0 < 0:
        raise ValueError(
            f"Computed negative susceptible initial state for s_frac={s_frac}: {s0}",
        )
    r0_init = n0 - s0 - s0_non_u - i0_total - h0_total - r0_non_u
    if r0_init < 0:
        raise ValueError(
            f"Computed negative recovered initial state for s_frac={s_frac}: {r0_init}",
        )

    _set_param(cfg, "r0", r0_value)
    _set_param(cfg, "s0__vax_u", s0)
    _set_param(cfg, "r0__vax_u", r0_init)

    out_dir.mkdir(parents=True, exist_ok=True)
    _set_backend_root(cfg, str(out_dir))

    with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as tmp:
        yaml.safe_dump(cfg, tmp, sort_keys=False)
        tmp_cfg_path = Path(tmp.name)

    try:
        subprocess.run(
            [
                "flepimop2",
                "simulate",
                str(tmp_cfg_path),
                "-t",
                "scenario_sweep",
            ],
            check=True,
            cwd=cfg_path.parent.parent,
        )
    finally:
        tmp_cfg_path.unlink(missing_ok=True)


def _make_panel_figure(
    panel_data: dict[tuple[float, float], np.ndarray],
    t_start_vals: list[float],
    cap_l_vals: list[float],
    r0_values: list[float],
    s_frac_values: list[float],
    default_t_start: float,
    default_cap_l: float,
    out_path: Path,
) -> None:
    """Render 3x3 heatmap panel with per-panel color limits."""
    fig, axes = plt.subplots(
        nrows=len(s_frac_values),
        ncols=len(r0_values),
        figsize=(16, 12),
        sharex=True,
        sharey=True,
    )

    if len(s_frac_values) == 1 and len(r0_values) == 1:
        axes = np.array([[axes]])
    elif len(s_frac_values) == 1:
        axes = np.array([axes])
    elif len(r0_values) == 1:
        axes = np.array([[ax] for ax in axes])

    default_x = _find_value_index([float(v) for v in t_start_vals], default_t_start)
    default_y = _find_value_index([float(v) for v in cap_l_vals], default_cap_l)

    im = None
    for row, s_frac in enumerate(s_frac_values):
        for col, r0_val in enumerate(r0_values):
            ax = axes[row, col]
            pct_change = panel_data[(r0_val, s_frac)]

            local_abs = float(np.abs(pct_change).max())
            local_vmax = max(1.0, float(math.ceil(local_abs)))

            im = ax.imshow(
                pct_change,
                cmap="RdYlGn_r",
                aspect="auto",
                origin="lower",
                vmin=-local_vmax,
                vmax=local_vmax,
            )

            # Annotate each cell with its percent change value.
            for i in range(len(cap_l_vals)):
                for j in range(len(t_start_vals)):
                    val = pct_change[i, j]
                    text_color = "black" if abs(val) < (0.35 * local_vmax) else "white"
                    ax.text(
                        j,
                        i,
                        f"{val:+.1f}%",
                        ha="center",
                        va="center",
                        color=text_color,
                        fontsize=5.5,
                        fontweight="bold",
                    )

            if default_x is not None and default_y is not None:
                ax.add_patch(
                    Rectangle(
                        (default_x - 0.5, default_y - 0.5),
                        1.0,
                        1.0,
                        fill=False,
                        edgecolor="black",
                        linewidth=2.0,
                    ),
                )

            if row == 0:
                ax.set_title(
                    f"R0={r0_val:.1f} (±{local_vmax:.0f}%)",
                    fontsize=12,
                    fontweight="bold",
                )
            ax.set_xticks(range(len(t_start_vals)))
            ax.set_xticklabels([int(v) for v in t_start_vals], fontsize=8)
            ax.set_yticks(range(len(cap_l_vals)))
            ax.set_yticklabels([f"{v:.2f}" for v in cap_l_vals], fontsize=8)

            if col == 0:
                ax.text(
                    -0.35,
                    0.5,
                    f"S0={int(round(s_frac * 100))}%",
                    transform=ax.transAxes,
                    ha="right",
                    va="center",
                    fontsize=11,
                    fontweight="bold",
                )

            if row == len(s_frac_values) - 1:
                ax.set_xlabel("Campaign Start Time (days)")
            if col == 0:
                ax.set_ylabel("Vaccine Coverage Cap")

    if im is None:
        raise RuntimeError("No panels were rendered")

    # Reserve fixed margins for row labels and subplot titles.
    fig.subplots_adjust(
        left=0.16,
        right=0.95,
        bottom=0.08,
        top=0.90,
        wspace=0.09,
        hspace=0.06,
    )

    fig.suptitle(
        (
            "Hospitalization Burden Across Vaccination Policy by R0 and Initial Susceptible Share\n"
            f"Panel baseline: t_start={default_t_start:g}, cap_l={default_cap_l:g}"
        ),
        fontsize=14,
        fontweight="bold",
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = sys.argv[1:]
    if len(args) < ARG_LEN_MIN:
        msg = (
            "python postprocessing/scenario_heatmap_3x3.py <config.yml> <output.png> "
            "[--run]"
        )
        raise SystemExit(msg)

    cfg_path = Path(args[0])
    out_path = Path(args[1])
    run_simulations = "--run" in args[2:]

    config_model = ConfigurationModel.from_yaml(cfg_path)
    t_start_vals = _scenario_param_values(
        config_model,
        SWEEP_SCENARIO_NAME,
        "t_start",
    )
    cap_l_vals = _scenario_param_values(
        config_model,
        SWEEP_SCENARIO_NAME,
        "cap_l",
    )
    r0_values = _scenario_param_values(
        config_model,
        PANEL_SCENARIO_NAME,
        "r0",
    )
    s_frac_values = _scenario_param_values(
        config_model,
        PANEL_SCENARIO_NAME,
        "s_frac",
    )
    default_t_start = float(config_model.parameters["t_start"].value)
    default_cap_l = float(config_model.parameters["cap_l"].value)

    base_root = Path("model_output") / "r0_s0_batches"
    panel_data: dict[tuple[float, float], np.ndarray] = {}

    if run_simulations:
        with cfg_path.open() as f:
            base_cfg = yaml.safe_load(f)

        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        batch_root = base_root / stamp
        batch_root.mkdir(parents=True, exist_ok=True)

        for r0_val in r0_values:
            for s_frac in s_frac_values:
                panel_dir = batch_root / (
                    f"r0_{_slug_float(r0_val)}__sfrac_{_slug_float(s_frac)}"
                )
                print(
                    f"Running panel simulation: R0={r0_val:.1f}, S0={s_frac:.1%} -> {panel_dir}",
                )
                _run_panel_simulation(base_cfg, cfg_path, panel_dir, r0_val, s_frac)
                panel_data[(r0_val, s_frac)] = _extract_panel_matrix(
                    panel_dir,
                    t_start_vals,
                    cap_l_vals,
                    default_t_start,
                    default_cap_l,
                )

        latest_txt = base_root / "LATEST"
        latest_txt.write_text(stamp)
    else:
        latest_txt = base_root / "LATEST"
        if not latest_txt.exists():
            raise FileNotFoundError(
                "No batch marker found. Run with --run once to generate panel outputs.",
            )
        stamp = latest_txt.read_text().strip()
        batch_root = base_root / stamp

        for r0_val in r0_values:
            for s_frac in s_frac_values:
                panel_dir = batch_root / (
                    f"r0_{_slug_float(r0_val)}__sfrac_{_slug_float(s_frac)}"
                )
                panel_data[(r0_val, s_frac)] = _extract_panel_matrix(
                    panel_dir,
                    t_start_vals,
                    cap_l_vals,
                    default_t_start,
                    default_cap_l,
                )

    _make_panel_figure(
        panel_data,
        t_start_vals,
        cap_l_vals,
        r0_values,
        s_frac_values,
        default_t_start,
        default_cap_l,
        out_path,
    )
    print(f"3x3 panel heatmap saved to {out_path}")


if __name__ == "__main__":
    main()
