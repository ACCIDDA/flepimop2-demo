"""Plot classic vs linear-chain SIR using existing CSV outputs.

This script reads the latest CSVs produced by the first two simulate targets in
the provided flepimop2 config and renders a side-by-side plot. It does not run
any simulations; it only consumes the data already written to the configured
CSV backends.
"""

from __future__ import annotations

import sys
from collections import OrderedDict
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from flepimop2.configuration import ConfigurationModel

ARG_LEN = 2


def _latest_csv(results_dir: Path) -> Path:
    csvs = sorted(results_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime)
    if not csvs:
        raise FileNotFoundError(f"No CSV files found in {results_dir}")
    return csvs[-1]


def _resolve_results_dir(
    config_model: ConfigurationModel, simulate_name: str | None = None
) -> Path:
    """Resolve the CSV backend output directory for a simulate target."""

    simulate_block = config_model.simulate
    if not simulate_block:
        raise ValueError("config.simulate must be non-empty")

    if simulate_name is None:
        simulate_cfg = next(iter(simulate_block.values()))
    else:
        simulate_cfg = simulate_block.get(simulate_name)
        if simulate_cfg is None:
            raise KeyError(f"simulate target {simulate_name!r} not found")

    backend_name = getattr(simulate_cfg, "backend", None) or "default"
    backend_model = config_model.backends.get(backend_name)
    if backend_model is None:
        raise KeyError(f"backend {backend_name!r} not found in config.backends")

    backend_cfg = backend_model.model_dump()

    root = (
        backend_cfg.get("root")
        or backend_cfg.get("config", {}).get("root")
        or backend_cfg.get("params", {}).get("root")
        or backend_cfg.get("settings", {}).get("root")
        or "model_output"
    )

    return Path(root)


def plot_compare(classic_csv: Path, linear_csv: Path, out_path: Path) -> None:
    df_classic = pd.read_csv(classic_csv, header=None)
    df_linear = pd.read_csv(linear_csv, header=None)

    if df_classic.shape[1] < 4:
        raise ValueError("Classic CSV must have at least 4 columns (t,S,I,R)")
    if df_linear.shape[1] < 6:
        raise ValueError(
            "Linear-chain CSV must have at least 6 columns (t,S,I1,I2,I3,R)"
        )

    df_classic = df_classic.iloc[:, :4]
    df_classic.columns = ["time", "S", "I", "R"]

    df_linear = df_linear.iloc[:, :6]
    df_linear.columns = ["time", "S", "I1", "I2", "I3", "R"]
    df_linear["I_total"] = df_linear[["I1", "I2", "I3"]].sum(axis=1)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)

    axes[0].plot(df_classic["time"], df_classic["S"], label="S")
    axes[0].plot(df_classic["time"], df_classic["I"], label="I")
    axes[0].plot(df_classic["time"], df_classic["R"], label="R")
    axes[0].set_title("Classic SIR")
    axes[0].set_xlabel("Time")
    axes[0].set_ylabel("Population")
    axes[0].grid(True)
    axes[0].legend()

    axes[1].plot(df_linear["time"], df_linear["S"], label="S")
    axes[1].plot(df_linear["time"], df_linear["I_total"], label="I = I1+I2+I3")
    axes[1].plot(df_linear["time"], df_linear["R"], label="R")
    axes[1].set_title("Linear-chain SIR")
    axes[1].set_xlabel("Time")
    axes[1].grid(True)
    axes[1].legend()

    fig.suptitle("Classic vs Linear-chain SIR (same beta/gamma)")
    fig.tight_layout()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150)
    plt.close(fig)


def main() -> None:
    args = sys.argv[1:]
    if len(args) != ARG_LEN:
        raise SystemExit(
            "Usage: python postprocessing/SIR_linear_chain_compare_op_engine.py <config.yml> <output.png>"
        )

    cfg_path = Path(args[0])
    out_path = Path(args[1])

    config_model = ConfigurationModel.from_yaml(cfg_path)

    simulate_names = list(OrderedDict(config_model.simulate).keys())
    if len(simulate_names) < 2:
        raise ValueError("Config must define at least two simulate targets")

    classic_name, linear_name = simulate_names[:2]

    classic_dir = _resolve_results_dir(config_model, classic_name)
    linear_dir = _resolve_results_dir(config_model, linear_name)

    classic_csv = _latest_csv(classic_dir)
    linear_csv = _latest_csv(linear_dir)

    plot_compare(classic_csv, linear_csv, out_path)


if __name__ == "__main__":
    main()
