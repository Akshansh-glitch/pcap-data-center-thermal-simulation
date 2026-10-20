"""Binary protocol for the native solver; all four fields are row-major float32."""
from __future__ import annotations
import os
import platform
import shutil
import subprocess
import time
import uuid
from pathlib import Path
import numpy as np
from .model import ROOT


def engine_path() -> Path:
    override = os.environ.get("THERMAL_ENGINE")
    candidates = [Path(override)] if override else []
    candidates += [ROOT / "build" / "thermal_engine.exe", ROOT / "build" / "thermal_engine",
                   ROOT / "build" / "Release" / "thermal_engine.exe"]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError("Native thermal_engine is missing. Build it first; see README.")


def environment_info() -> dict:
    info = {"system": platform.platform(), "cpu": platform.processor(),
            "nvcc": shutil.which("nvcc") or "unavailable"}
    if shutil.which("nvidia-smi"):
        try:
            p = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                               capture_output=True, text=True, timeout=5)
            info["gpu"] = p.stdout.strip() if p.returncode == 0 else "unavailable"
        except (OSError, subprocess.TimeoutExpired):
            info["gpu"] = "unavailable"
    else:
        info["gpu"] = "unavailable"
    return info


def run_native(c: dict, temperature: np.ndarray, heat: np.ndarray,
               cooling: np.ndarray, air: np.ndarray, steps: int = 1,
               solver: str | None = None, threads: int | None = None,
               block_size: int | None = None) -> tuple[np.ndarray, dict]:
    exe = engine_path()
    shape = (c["rows"], c["cols"])
    arrays = (temperature, heat, cooling, air)
    if any(a.shape != shape for a in arrays):
        raise ValueError("field shape mismatch")
    if steps < 1:
        raise ValueError("steps must be positive")
    scratch = ROOT / "build"
    if not scratch.is_dir():
        raise FileNotFoundError("Build directory is missing")
    token = uuid.uuid4().hex
    source, dest = scratch / f"thermal-{token}-in.bin", scratch / f"thermal-{token}-out.bin"
    try:
        with source.open("wb") as f:
            for a in arrays:
                np.ascontiguousarray(a, dtype="<f4").tofile(f)
        args = [str(exe), str(source), str(dest), str(c["rows"]), str(c["cols"]),
                str(steps), str(c["dt"]), str(c["dx"]), str(c["dy"]),
                str(c["rho_cp"]), str(c["conductivity"]), str(c["ambient"]),
                solver or c["solver"], str(threads if threads is not None else c["threads"]),
                str(block_size if block_size is not None else c["block_size"]), "v1"]
        start = time.perf_counter()
        p = subprocess.run(args, capture_output=True, text=True, timeout=300)
        wall_ms = (time.perf_counter() - start) * 1000
        if p.returncode:
            raise RuntimeError(p.stderr.strip() or f"native engine failed ({p.returncode})")
        data = np.fromfile(dest, dtype="<f4")
        if data.size != shape[0] * shape[1]:
            raise RuntimeError("native engine produced an incomplete output")
        metrics = dict(line.split("=", 1) for line in p.stdout.splitlines() if "=" in line)
        metrics = {k: float(v) if k.endswith("_ms") else v for k, v in metrics.items()}
        metrics["end_to_end_ms"] = wall_ms
        return data.reshape(shape), metrics
    finally:
        source.unlink(missing_ok=True)
        dest.unlink(missing_ok=True)
