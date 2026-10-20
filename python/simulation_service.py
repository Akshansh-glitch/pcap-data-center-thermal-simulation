"""Stateful stepping; changing overrides influences the next physical update."""
from __future__ import annotations
import copy
import time
import numpy as np
from .analytics import summarize
from .engine_bridge import run_native
from .model import fields, initial_state, validate_config


class Simulation:
    def __init__(self, config: dict):
        validate_config(config)
        self.config = copy.deepcopy(config)
        self.temperature = initial_state(config)
        self.step = 0
        self.overrides: dict[tuple[int, int], dict] = {}
        self.history: list[dict] = []
        self.last_fields = fields(config, 0)
        self.last_timing: dict = {}

    def advance(self, count: int = 1, on_step=None):
        if count < 1:
            raise ValueError("count must be positive")
        for _ in range(count):
            self.last_fields = fields(self.config, self.step, self.overrides)
            _, _, heat, cooling, air = self.last_fields
            self.temperature, self.last_timing = run_native(self.config, self.temperature,
                                                              heat, cooling, air)
            self.step += 1
            record = {"step": self.step, "time_s": self.step * self.config["dt"],
                      "dt": self.config["dt"], **summarize(self.temperature, self.config["hotspot_threshold"])}
            self.history.append(record)
            if on_step is not None:
                on_step(self.step, count)
        return self.temperature

    def set_cell(self, row: int, col: int, utilization=None, cooling=None):
        if not (0 <= row < self.config["rows"] and 0 <= col < self.config["cols"]):
            raise ValueError("cell outside grid")
        value = self.overrides.setdefault((row, col), {})
        if utilization is not None:
            if not 0 <= utilization <= 1: raise ValueError("utilization outside [0,1]")
            value["utilization"] = float(utilization)
        if cooling is not None:
            if cooling < 0: raise ValueError("cooling must be nonnegative")
            value["cooling"] = float(cooling)

    def reset(self):
        self.temperature = initial_state(self.config)
        self.step = 0
        self.history.clear()
        self.overrides.clear()
        self.last_fields = fields(self.config, 0)
