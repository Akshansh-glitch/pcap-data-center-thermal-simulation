"""Deterministic scenario inputs and physically dimensioned model validation."""
from __future__ import annotations
import copy
import json
import math
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = json.loads((ROOT / "config" / "default_config.json").read_text())
PATTERNS = ("steady", "random", "periodic", "spike", "localized", "moving")


def default_config() -> dict:
    return copy.deepcopy(DEFAULT)


def baseline_config() -> dict:
    """Sample without the built-in cooling failure, for strategy comparison."""
    c = default_config()
    c["failure_start"] = 1_000_000_000
    return c


def validate_config(c: dict) -> None:
    for key in ("rows", "cols", "steps", "period", "seed"):
        if not isinstance(c[key], int) or c[key] < (1 if key != "seed" else 0):
            raise ValueError(f"{key} must be a positive integer")
    if c["rows"] * c["cols"] > 100_000_000:
        raise ValueError("grid exceeds 100 million cells")
    positive = ("dt", "dx", "dy", "rho_cp", "cell_volume")
    nonnegative = ("conductivity", "cooling", "idle_power", "max_power")
    for key in positive + nonnegative + ("initial_temp", "ambient", "air_temp", "base_utilization", "amplitude", "hotspot_threshold", "spike_utilization", "failure_factor"):
        v = c[key]
        if not isinstance(v, (int, float)) or not math.isfinite(v) or (key in positive and v <= 0) or (key in nonnegative and v < 0):
            raise ValueError(f"invalid {key}")
    if c["max_power"] < c["idle_power"]:
        raise ValueError("max_power must be at least idle_power")
    for key in ("base_utilization", "spike_utilization", "failure_factor"):
        if not 0 <= c[key] <= 1:
            raise ValueError(f"{key} must be in [0,1]")
    if c["amplitude"] > 1 or c["pattern"] not in PATTERNS:
        raise ValueError("invalid workload pattern or amplitude")
    if c["solver"] not in ("cpu", "openmp", "cuda", "cuda-shared"):
        raise ValueError("invalid solver")
    r = c["region"]
    if any(not isinstance(r[k], int) for k in ("row", "col", "height", "width")) or r["row"] < 0 or r["col"] < 0 or r["height"] < 1 or r["width"] < 1 or r["row"] + r["height"] > c["rows"] or r["col"] + r["width"] > c["cols"]:
        raise ValueError("region lies outside grid")
    if 2 * c["conductivity"] * c["dt"] / c["rho_cp"] * (1/c["dx"]**2 + 1/c["dy"]**2) + c["cooling"] * c["dt"] / c["rho_cp"] > 1 + 1e-7:
        raise ValueError("unstable timestep: reduce dt, conductivity, or cooling")
    for event in c.get("events", []):
        if not isinstance(event.get("step"), int) or event["step"] < 0 or event.get("kind") not in ("workload", "cooling", "redistribute", "restore_cooling"):
            raise ValueError("invalid scheduled event")
        if event["kind"] in ("workload", "cooling") and (not isinstance(event.get("value"), (int,float)) or not math.isfinite(event["value"]) or event["value"] < 0):
            raise ValueError("invalid event value")
        if event["kind"] == "workload" and event["value"] > 1:
            raise ValueError("workload event must be in [0,1]")


def region_slice(c: dict):
    r = c["region"]
    return np.s_[r["row"]:r["row"]+r["height"], r["col"]:r["col"]+r["width"]]


def workload(c: dict, step: int) -> np.ndarray:
    rows, cols = c["rows"], c["cols"]
    base = c["base_utilization"]
    u = np.full((rows, cols), base, dtype=np.float32)
    pattern = c["pattern"]
    if pattern == "random":
        # Step-specific seeds preserve reproducibility after pause/resume.
        u[:] = base + c["amplitude"] * (np.random.default_rng(c["seed"] + step).random((rows, cols)) - 0.5) * 2
    elif pattern == "periodic":
        u[:] = base + c["amplitude"] * math.sin(2 * math.pi * step / c["period"])
    elif pattern == "spike" and step >= c["spike_start"]:
        u[:] = c["spike_utilization"]
    elif pattern == "localized":
        u[region_slice(c)] = c["spike_utilization"]
    elif pattern == "moving":
        r = c["region"]
        top = r["row"]
        left = (r["col"] + step) % max(1, cols - r["width"] + 1)
        u[top:top+r["height"], left:left+r["width"]] = c["spike_utilization"]
    return np.clip(u, 0, 1)


def fields(c: dict, step: int, overrides: dict | None = None):
    overrides = overrides or {}
    u = workload(c, step)
    cooling = np.full(u.shape, c["cooling"], dtype=np.float32)
    if step >= c["failure_start"]:
        cooling[region_slice(c)] *= c["failure_factor"]
    for event in sorted(c.get("events", []), key=lambda e: e["step"]):
        if event["step"] > step:
            break
        if event["kind"] == "workload":
            u[:] = event["value"]
        elif event["kind"] == "cooling":
            cooling[:] = event["value"]
        elif event["kind"] == "redistribute":
            # Shift load from selected region to the rest of the grid, conserving total utilization.
            sl = region_slice(c)
            removed = float(u[sl].sum()) * 0.5
            u[sl] *= 0.5
            outside = np.ones(u.shape, bool)
            outside[sl] = False
            u[outside] += removed / max(1, outside.sum())
        elif event["kind"] == "restore_cooling":
            cooling[:] = c["cooling"]
    for (r, col), changes in overrides.items():
        if "utilization" in changes:
            u[r, col] = changes["utilization"]
        if "cooling" in changes:
            cooling[r, col] = changes["cooling"]
    u = np.clip(u, 0, 1).astype(np.float32)
    power = c["idle_power"] + u * (c["max_power"] - c["idle_power"])
    heat = (power / c["cell_volume"]).astype(np.float32)  # W/m³
    air = np.full(u.shape, c["air_temp"], dtype=np.float32)
    if np.any(cooling < 0):
        raise ValueError("cooling must be nonnegative")
    effective = 2 * c["conductivity"] * c["dt"] / c["rho_cp"] * (1/c["dx"]**2 + 1/c["dy"]**2) + float(cooling.max()) * c["dt"] / c["rho_cp"]
    if effective > 1 + 1e-7:
        raise ValueError("event or override makes timestep unstable")
    return u, power.astype(np.float32), heat, cooling, air


def initial_state(c: dict) -> np.ndarray:
    t = np.full((c["rows"], c["cols"]), c["initial_temp"], dtype=np.float32)
    t[0, :] = t[-1, :] = c["ambient"]
    t[:, 0] = t[:, -1] = c["ambient"]
    return t
