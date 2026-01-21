# postprocessing/SIR_plot_op_engine.py
"""OP Engine SIR plot generator."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import yaml

MIN_SIR_COLUMNS = 4
ARG_LEN = 2


def _latest_csv(results_dir: Path) -> Path:
    csvs = sorted(results_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime)
    if not csvs:
        msg = f"No CSV files found in results directory: {results_dir}"
        raise FileNotFoundError(msg)
    return csvs[-1]


def main() -> None:
    """Generate SIR plot from op_engine simulation results."""
    args = sys.argv[1:]
    if len(args) != ARG_LEN:
        msg = "python postprocessing/SIR_plot_op_engine.py <config.yml> <output.png>"
        raise SystemExit(msg)

    cfg_path = Path(args[0])
    out_path = Path(args[1])

    with cfg_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    backend_cfg = config.get("backend", [])
    if isinstance(backend_cfg, list):
        # Normalize list-form backend to a named mapping like the R script does.
        backend_cfg = {"default": backend_cfg[0]} if backend_cfg else {"default": {}}

    simulate_cfg = config.get("simulate", {})
    # Use the first simulate target by insertion order (matches CLI default behavior).
    if not isinstance(simulate_cfg, dict) or not simulate_cfg:
        msg = "config.simulate must be a non-empty mapping"
        raise ValueError(msg)

    first_sim_name = next(iter(simulate_cfg))
    first_sim = simulate_cfg[first_sim_name]
    backend_name = first_sim.get("backend", "default")

    backend = backend_cfg.get(backend_name, {})
    results_path = Path(backend.get("root", "model_output"))

    latest = _latest_csv(results_path)
    df = pd.read_csv(latest, header=None)

    # Expect (T, 1 + n_state) => time + SIR columns
    if df.shape[1] < MIN_SIR_COLUMNS:
        msg = f"Expected at least 4 columns (time,S,I,R); got {df.shape[1]}"
        raise ValueError(msg)

    df = df.iloc[:, :4]
    df.columns = ["time", "S", "I", "R"]

    plt.figure(figsize=(6, 4))
    plt.plot(df["time"], df["S"], label="S")
    plt.plot(df["time"], df["I"], label="I")
    plt.plot(df["time"], df["R"], label="R")
    plt.grid(visible=True)
    plt.legend()
    plt.xlabel("Time")
    plt.ylabel("Value")
    plt.title("SIR (op_engine via flepimop2)")
    plt.tight_layout()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150)
    plt.close()


if __name__ == "__main__":
    main()
