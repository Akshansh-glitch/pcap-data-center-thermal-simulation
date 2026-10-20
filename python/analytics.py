"""Statistics are always calculated from the full numerical grid."""
from __future__ import annotations
import numpy as np


def summarize(temperature: np.ndarray, threshold: float) -> dict:
    if temperature.size == 0 or not np.all(np.isfinite(temperature)):
        raise ValueError("temperature grid must be nonempty and finite")
    hot = temperature > threshold
    return {"min": float(temperature.min()), "mean": float(temperature.mean()),
            "max": float(temperature.max()), "std": float(temperature.std()),
            "hotspot_count": int(hot.sum()), "hotspot_pct": 100 * float(hot.mean())}


def timeline_metrics(history: list[dict], threshold: float, events: list[dict] | None = None) -> dict:
    if not history:
        return {"first_crossing_step": None, "hotspot_duration_s": 0.0,
                "recovery_time_s": None}
    crossing = next((x["step"] for x in history if x["max"] > threshold), None)
    recovery = None
    for event in events or []:
        if event.get("kind") != "restore_cooling":
            continue
        earlier_hot = any(x["hotspot_count"] > 0 for x in history if x["step"] <= event["step"])
        if earlier_hot:
            clear = next((x for x in history if x["step"] >= event["step"] and x["hotspot_count"] == 0), None)
            if clear:
                recovery = max(0, clear["step"] - event["step"]) * clear["dt"]
                break
    return {"first_crossing_step": crossing,
            "hotspot_duration_s": sum(x["dt"] for x in history if x["hotspot_count"] > 0),
            "recovery_time_s": recovery}
