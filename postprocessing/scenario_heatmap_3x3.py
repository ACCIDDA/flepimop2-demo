"""Run coarse t_start/S0 sweeps and generate a 3x3 panel of heatmaps.

Rows: susceptible share at t=0 (S0 fraction): 30%, 50%, 70%
Cols: campaign start time t_start (days): 0, 35, 70

Each panel is an r0 x cap_l heatmap (% change from panel default policy),
with a box around the default policy cell.
"""

from __future__ import annotations

import copy
import logging
import math
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from flepimop2.configuration import ConfigurationModel
from matplotlib.patches import Rectangle

if TYPE_CHECKING:
    from matplotlib.axes import Axes

ARG_LEN_MIN = 2
SWEEP_SCENARIO_NAME = "vax_campaign"
PANEL_SCENARIO_NAME = "panel_grid"
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlotMeta:
    """Metadata used to render and label the panel figure."""

    r0_vals: list[float]
    cap_l_vals: list[float]
    t_start_values: list[float]
    s_frac_values: list[float]
    default_r0: float
    default_cap_l: float
    out_path: Path


@dataclass(frozen=True)
class PanelDrawMeta:
    """Metadata needed to draw one subplot panel."""

    t_start: float
    s_frac: float
    show_title: bool
    show_row_label: bool
    show_xlabel: bool
    r0_vals: list[float]
    cap_l_vals: list[float]
    default_x: int | None
    default_y: int | None


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
    time = df.iloc[:, 0].to_numpy()
    return float(np.trapezoid(h_totals.to_numpy(), time))


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
        msg = f"Missing parameter '{name}' in config"
        raise KeyError(msg)
    params[name]["value"] = float(value)


def _set_backend_root(cfg: dict, root: str) -> None:
    backend = cfg.get("backend", [])
    if not backend:
        msg = "Config has no backend section"
        raise ValueError(msg)
    if not isinstance(backend, list):
        msg = "backend section must be a list"
        raise TypeError(msg)
    backend[0]["root"] = root


def _scenario_param_values(
    cfg: dict[str, Any],
    scenario_name: str,
    param_name: str,
) -> list[float]:
    """Read scenario parameter values from raw YAML config."""
    scenarios = cfg.get("scenarios")
    if not isinstance(scenarios, dict):
        msg = "No scenarios mapping found in config"
        raise TypeError(msg)
    scenario = scenarios.get(scenario_name)
    if not isinstance(scenario, dict):
        msg = f"Scenario {scenario_name!r} not found in config.scenarios"
        raise KeyError(msg)
    params = scenario.get("parameters")
    if not isinstance(params, dict):
        msg = f"Scenario {scenario_name!r} has no parameters mapping"
        raise TypeError(msg)
    if param_name not in params:
        msg = f"Parameter {param_name!r} not found in scenarios[{scenario_name!r}]"
        raise KeyError(msg)
    return [float(v) for v in params[param_name]]


def _extract_panel_matrix(
    results_dir: Path,
    r0_vals: list[float],
    cap_l_vals: list[float],
    default_r0: float,
    default_cap_l: float,
) -> np.ndarray:
    """Build panel matrix as % change from panel default policy."""
    csv_files = _latest_csv_by_index(results_dir)
    expected = len(r0_vals) * len(cap_l_vals)
    if len(csv_files) != expected:
        msg = (
            f"Expected {expected} scenario files in {results_dir}, "
            f"found {len(csv_files)}. "
            "Check that scenario_sweep completed for this panel."
        )
        raise ValueError(msg)

    h_col_indices = [7, 8, 9]
    outcomes = np.zeros((len(cap_l_vals), len(r0_vals)))

    for scenario_idx, csv_file in enumerate(csv_files):
        df = pd.read_csv(csv_file, header=None)
        total_hosp = _compute_total_hospitalizations(df, h_col_indices)

        # product(r0, cap_l): cap_l is the fast axis.
        r0_idx = scenario_idx // len(cap_l_vals)
        cap_l_idx = scenario_idx % len(cap_l_vals)
        outcomes[cap_l_idx, r0_idx] = total_hosp

    default_x = _find_value_index([float(v) for v in r0_vals], default_r0)
    default_y = _find_value_index([float(v) for v in cap_l_vals], default_cap_l)
    if default_x is None or default_y is None:
        msg = "Default r0/cap_l is not on scenario grid"
        raise ValueError(msg)

    baseline = outcomes[default_y, default_x]
    if baseline <= 0:
        msg = f"Non-positive panel baseline in {results_dir}: {baseline}"
        raise ValueError(msg)

    return (outcomes / baseline - 1.0) * 100.0


def _run_panel_simulation(
    base_cfg: dict,
    cfg_path: Path,
    out_dir: Path,
    t_start_value: float,
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
        msg = f"Computed negative susceptible initial state for s_frac={s_frac}: {s0}"
        raise ValueError(msg)
    r0_init = n0 - s0 - s0_non_u - i0_total - h0_total - r0_non_u
    if r0_init < 0:
        msg = (
            f"Computed negative recovered initial state for s_frac={s_frac}: {r0_init}"
        )
        raise ValueError(msg)

    _set_param(cfg, "t_start", t_start_value)
    _set_param(cfg, "s0__vax_u", s0)
    _set_param(cfg, "r0__vax_u", r0_init)

    out_dir.mkdir(parents=True, exist_ok=True)
    _set_backend_root(cfg, str(out_dir))

    with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as tmp:
        yaml.safe_dump(cfg, tmp, sort_keys=False)
        tmp_cfg_path = Path(tmp.name)

    try:
        flepimop2_exe = shutil.which("flepimop2")
        if flepimop2_exe is None:
            msg = "flepimop2 executable not found in PATH"
            raise FileNotFoundError(msg)
        subprocess.run(  # noqa: S603
            [
                flepimop2_exe,
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


def _normalize_axes(
    axes: np.ndarray,
    n_rows: int,
    n_cols: int,
) -> np.ndarray:
    """Normalize matplotlib subplot axes to a 2D array."""
    if n_rows == 1 and n_cols == 1:
        return np.array([[axes]])
    if n_rows == 1:
        return np.array([axes])
    if n_cols == 1:
        return np.array([[ax] for ax in axes])
    return axes


def _annotate_panel(
    ax: Axes,
    pct_change: np.ndarray,
    local_vmax: float,
    panel_meta: PanelDrawMeta,
) -> None:
    """Add per-cell percent labels to a panel heatmap."""
    for i in range(len(panel_meta.cap_l_vals)):
        for j in range(len(panel_meta.r0_vals)):
            if (
                panel_meta.default_x is not None
                and panel_meta.default_y is not None
                and i == panel_meta.default_y
                and j == panel_meta.default_x
            ):
                continue
            val = float(pct_change[i, j])
            text_color = "black" if abs(val) < (0.35 * local_vmax) else "white"
            rounded_pct = round(val)
            ax.text(
                j,
                i,
                f"{rounded_pct:+d}%",
                ha="center",
                va="center",
                color=text_color,
                fontsize=5.5,
                fontweight="bold",
            )


def _draw_panel(
    ax: Axes,
    pct_change: np.ndarray,
    local_vmax: float,
    panel_meta: PanelDrawMeta,
) -> None:
    """Draw one panel heatmap and its labels/annotations."""
    ax.imshow(
        pct_change,
        cmap="RdYlGn_r",
        aspect="auto",
        origin="lower",
        vmin=-local_vmax,
        vmax=local_vmax,
    )
    _annotate_panel(
        ax,
        pct_change,
        local_vmax,
        panel_meta,
    )

    if panel_meta.default_x is not None and panel_meta.default_y is not None:
        ax.add_patch(
            Rectangle(
                (panel_meta.default_x - 0.5, panel_meta.default_y - 0.5),
                1.0,
                1.0,
                fill=False,
                edgecolor="black",
                linewidth=2.0,
            ),
        )

    if panel_meta.show_title:
        ax.set_title(
            f"t_start={panel_meta.t_start:.0f}d (±{local_vmax:.0f}%)",
            fontsize=12,
            fontweight="bold",
        )

    ax.set_xticks(range(len(panel_meta.r0_vals)))
    ax.set_xticklabels([f"{v:.2f}" for v in panel_meta.r0_vals], fontsize=8)
    ax.set_yticks(range(len(panel_meta.cap_l_vals)))
    ax.set_yticklabels([f"{v:.2f}" for v in panel_meta.cap_l_vals], fontsize=8)

    if panel_meta.show_row_label:
        ax.text(
            -0.35,
            0.5,
            f"S0={round(panel_meta.s_frac * 100)}%",
            transform=ax.transAxes,
            ha="right",
            va="center",
            fontsize=11,
            fontweight="bold",
        )
        ax.set_ylabel("Vaccine Coverage Cap")

    if panel_meta.show_xlabel:
        ax.set_xlabel("Basic Reproduction Number (R0)")


def _make_panel_figure(
    panel_data: dict[tuple[float, float], np.ndarray],
    meta: PlotMeta,
) -> None:
    """Render 3x3 heatmap panel with per-panel color limits."""
    fig, axes = plt.subplots(
        nrows=len(meta.s_frac_values),
        ncols=len(meta.t_start_values),
        figsize=(16, 12),
        sharex=True,
        sharey=True,
    )

    axes = _normalize_axes(axes, len(meta.s_frac_values), len(meta.t_start_values))
    default_x = _find_value_index(
        [float(v) for v in meta.r0_vals],
        meta.default_r0,
    )
    default_y = _find_value_index(
        [float(v) for v in meta.cap_l_vals],
        meta.default_cap_l,
    )

    for row, s_frac in enumerate(meta.s_frac_values):
        for col, t_start in enumerate(meta.t_start_values):
            ax = axes[row, col]
            pct_change = panel_data[(t_start, s_frac)]

            local_abs = float(np.abs(pct_change).max())
            local_vmax = max(1.0, float(math.ceil(local_abs)))

            panel_meta = PanelDrawMeta(
                t_start=t_start,
                s_frac=s_frac,
                show_title=row == 0,
                show_row_label=col == 0,
                show_xlabel=row == len(meta.s_frac_values) - 1,
                r0_vals=meta.r0_vals,
                cap_l_vals=meta.cap_l_vals,
                default_x=default_x,
                default_y=default_y,
            )
            _draw_panel(
                ax=ax,
                pct_change=pct_change,
                local_vmax=local_vmax,
                panel_meta=panel_meta,
            )

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
            "Hospitalization Burden Across Vaccination Policy by "
            "Campaign Start Time and "
            "Initial Susceptible Share\n"
            f"Panel baseline: r0={meta.default_r0:g}, "
            f"cap_l={meta.default_cap_l:g}"
        ),
        fontsize=14,
        fontweight="bold",
    )
    meta.out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(meta.out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    """Run panel simulations (optional) and render the 3x3 scenario heatmap."""
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

    with cfg_path.open() as f:
        raw_cfg = yaml.safe_load(f)

    config_model = ConfigurationModel.from_yaml(cfg_path)
    r0_vals = _scenario_param_values(
        raw_cfg,
        SWEEP_SCENARIO_NAME,
        "r0",
    )
    cap_l_vals = _scenario_param_values(
        raw_cfg,
        SWEEP_SCENARIO_NAME,
        "cap_l",
    )
    t_start_values = _scenario_param_values(
        raw_cfg,
        PANEL_SCENARIO_NAME,
        "t_start",
    )
    s_frac_values = _scenario_param_values(
        raw_cfg,
        PANEL_SCENARIO_NAME,
        "s_frac",
    )
    default_r0 = float(config_model.parameters["r0"].value)
    default_cap_l = float(config_model.parameters["cap_l"].value)

    base_root = Path("model_output") / "tstart_s0_batches"
    panel_data: dict[tuple[float, float], np.ndarray] = {}

    if run_simulations:
        with cfg_path.open() as f:
            base_cfg = yaml.safe_load(f)

        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        batch_root = base_root / stamp
        batch_root.mkdir(parents=True, exist_ok=True)

        for t_start in t_start_values:
            for s_frac in s_frac_values:
                panel_dir = batch_root / (
                    f"tstart_{_slug_float(t_start)}__sfrac_{_slug_float(s_frac)}"
                )
                msg = (
                    "Running panel simulation: "
                    f"t_start={t_start:.0f}d, S0={s_frac:.1%} -> {panel_dir}"
                )
                LOGGER.info(msg)
                _run_panel_simulation(base_cfg, cfg_path, panel_dir, t_start, s_frac)
                panel_data[(t_start, s_frac)] = _extract_panel_matrix(
                    panel_dir,
                    r0_vals,
                    cap_l_vals,
                    default_r0,
                    default_cap_l,
                )

        latest_txt = base_root / "LATEST"
        latest_txt.write_text(stamp)
    else:
        latest_txt = base_root / "LATEST"
        if not latest_txt.exists():
            msg = (
                "No batch marker found. Run with --run once to generate panel outputs."
            )
            raise FileNotFoundError(msg)
        stamp = latest_txt.read_text().strip()
        batch_root = base_root / stamp

        for t_start in t_start_values:
            for s_frac in s_frac_values:
                panel_dir = batch_root / (
                    f"tstart_{_slug_float(t_start)}__sfrac_{_slug_float(s_frac)}"
                )
                panel_data[(t_start, s_frac)] = _extract_panel_matrix(
                    panel_dir,
                    r0_vals,
                    cap_l_vals,
                    default_r0,
                    default_cap_l,
                )

    plot_meta = PlotMeta(
        r0_vals=r0_vals,
        cap_l_vals=cap_l_vals,
        t_start_values=t_start_values,
        s_frac_values=s_frac_values,
        default_r0=default_r0,
        default_cap_l=default_cap_l,
        out_path=out_path,
    )
    _make_panel_figure(panel_data, plot_meta)
    sys.stdout.write(f"3x3 panel heatmap saved to {out_path}\n")


if __name__ == "__main__":
    main()
