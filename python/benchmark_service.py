"""Repeatable, measured comparisons with identical input arrays."""
from __future__ import annotations
import copy
import datetime as dt
import statistics
import platform
from pathlib import Path
import numpy as np
import pandas as pd
from .engine_bridge import run_native
from .model import ROOT, fields, initial_state, validate_config


def benchmark(config: dict, sizes: list[int], steps: int, solvers: list[str],
              repeats: int = 3, threads: int = 4, block_size: int = 256,
              progress=None) -> pd.DataFrame:
    rows = []
    total = len(sizes) * len(solvers)
    done = 0
    for size in sizes:
        c = copy.deepcopy(config)
        c.update(rows=size, cols=size, steps=steps, pattern="steady", failure_start=steps+1)
        c["events"] = []
        c["region"] = {"row": size//4, "col": size//4,
                       "height": max(1, size//4), "width": max(1, size//4)}
        validate_config(c)
        initial = initial_state(c)
        _, _, heat, cooling, air = fields(c, 0)
        reference, _ = run_native(c, initial, heat, cooling, air, steps, "cpu", threads, block_size)
        baseline_samples, baseline_wall = [], []
        for _ in range(repeats):
            _, timing = run_native(c, initial, heat, cooling, air, steps, "cpu", threads, block_size)
            baseline_samples.append(timing["compute_ms"])
            baseline_wall.append(timing["end_to_end_ms"])
        baseline = statistics.median(baseline_samples)
        for solver in solvers:
            row = {"timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                   "grid_rows": size, "grid_cols": size, "timesteps": steps,
                   "implementation": solver, "thread_count": threads if solver == "openmp" else 1,
                   "block_size": block_size if solver.startswith("cuda") else None,
                   "cpu": platform.processor(), "success": False}
            try:
                samples, wall, kernel, transfer = [], [], [], []
                result = None
                if solver == "cpu":
                    samples = baseline_samples.copy()
                    result = reference
                    wall = baseline_wall.copy()
                    kernel = transfer = [0.0] * repeats
                else:
                    # Warm-up before measured repetitions.
                    run_native(c, initial, heat, cooling, air, 1, solver, threads, block_size)
                    for _ in range(repeats):
                        result, timing = run_native(c, initial, heat, cooling, air, steps,
                                                    solver, threads, block_size)
                        samples.append(timing["compute_ms"])
                        wall.append(timing["end_to_end_ms"])
                        kernel.append(timing["kernel_ms"])
                        transfer.append(timing["transfer_ms"])
                    row["gpu_name"] = timing.get("device", "") if solver.startswith("cuda") else ""
                error = np.abs(result.astype(np.float64) - reference.astype(np.float64))
                row.update(success=True, compute_time_ms=statistics.median(samples),
                           variability_ms=statistics.pstdev(samples),
                           end_to_end_time_ms=statistics.median(wall),
                           kernel_time_ms=statistics.median(kernel),
                           transfer_time_ms=statistics.median(transfer),
                           speedup=baseline/statistics.median(samples),
                           throughput=(size*size*steps)/(statistics.median(samples)/1000),
                           max_absolute_error=float(error.max()), mean_absolute_error=float(error.mean()),
                           within_tolerance=bool(error.max() <= 1e-3),
                           efficiency=(baseline/statistics.median(samples))/threads if solver == "openmp" else None)
            except Exception as exc:
                row["error"] = str(exc)
            rows.append(row)
            done += 1
            if progress: progress(done, total)
    return pd.DataFrame(rows)


def save_results(df: pd.DataFrame) -> Path:
    directory = ROOT / "data" / "benchmark_results"
    directory.mkdir(parents=True, exist_ok=True)
    name = dt.datetime.now(dt.timezone.utc).strftime("benchmark-%Y%m%dT%H%M%S%fZ.csv")
    path = directory / name
    df.to_csv(path, index=False)
    return path


def load_history(limit: int = 20) -> pd.DataFrame:
    directory = ROOT / "data" / "benchmark_results"
    paths = sorted(directory.glob("benchmark-*.csv"), reverse=True)[:limit] if directory.exists() else []
    frames = []
    for path in paths:
        try:
            frames.append(pd.read_csv(path))
        except (OSError, pd.errors.ParserError):
            continue
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
