"""Plot two-population SIR results from existing CSV output."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from flepimop2.configuration import ConfigurationModel

MIN_COLS = 7  # time + 6 state entries
ARG_LEN = 2


def _latest_csv(results_dir: Path) -> Path:
    csvs = sorted(results_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime)
    if not csvs:
        msg = f"No CSV files found in results directory: {results_dir}"
        raise FileNotFoundError(msg)
    return csvs[-1]


def _resolve_results_dir(
    config_model: ConfigurationModel, simulate_name: str | None = None
) -> Path:
    """Resolve the CSV backend output directory for a simulate target."""
    simulate_block = config_model.simulate
    if not simulate_block:
        msg = "config.simulate must be non-empty"
        raise ValueError(msg)

    if simulate_name is None:
        simulate_cfg = next(iter(simulate_block.values()))
    else:
        simulate_cfg = simulate_block.get(simulate_name)
        if simulate_cfg is None:
            msg = f"simulate target {simulate_name!r} not found"
            raise KeyError(msg)

    backend_name = getattr(simulate_cfg, "backend", None) or "default"
    backend_model = config_model.backends.get(backend_name)
    if backend_model is None:
        msg = f"backend {backend_name!r} not found in config.backends"
        raise KeyError(msg)

    backend_cfg = backend_model.model_dump()

    root = (
        backend_cfg.get("root")
        or backend_cfg.get("config", {}).get("root")
        or backend_cfg.get("params", {}).get("root")
        or backend_cfg.get("settings", {}).get("root")
        or "model_output"
    )

    return Path(root)


def main() -> None:
    """Load latest two-pop CSV and render side-by-side plots."""
    args = sys.argv[1:]
    if len(args) != ARG_LEN:
        msg = (
            "Usage: python postprocessing/SIR_two_pop_plot_op_engine.py "
            "<config.yml> <output.png>"
        )
        raise SystemExit(msg)

    cfg_path = Path(args[0])
    out_path = Path(args[1])

    config_model = ConfigurationModel.from_yaml(cfg_path)
    results_dir = _resolve_results_dir(config_model)
    latest = _latest_csv(results_dir)

    df = pd.read_csv(latest, header=None)
    if df.shape[1] < MIN_COLS:
        msg = (
            f"Expected at least {MIN_COLS} columns (t,S1,I1,R1,S2,I2,R2); got "
            f"{df.shape[1]}"
        )
        raise ValueError(msg)

    df = df.iloc[:, :7]
    df.columns = ["time", "S1", "I1", "R1", "S2", "I2", "R2"]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)

    axes[0].plot(df["time"], df["S1"], label="S1")
    axes[0].plot(df["time"], df["I1"], label="I1")
    axes[0].plot(df["time"], df["R1"], label="R1")
    axes[0].set_title("Population 1")
    axes[0].set_xlabel("Time")
    axes[0].set_ylabel("Population")
    axes[0].grid(visible=True)
    axes[0].legend()

    axes[1].plot(df["time"], df["S2"], label="S2")
    axes[1].plot(df["time"], df["I2"], label="I2")
    axes[1].plot(df["time"], df["R2"], label="R2")
    axes[1].set_title("Population 2")
    axes[1].set_xlabel("Time")
    axes[1].grid(visible=True)
    axes[1].legend()

    fig.suptitle("Two-Pop SIR with Mixing")
    fig.tight_layout()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
