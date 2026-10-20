import json
import pytest
from python.model import default_config
from python.scenario_service import save_scenario, load_scenario
from python.benchmark_service import benchmark


def test_scenario_roundtrip():
    c=default_config()
    from python.model import ROOT
    directory=ROOT / "data" / "scenarios"
    path=save_scenario("Cooling Failure 1",c,directory)
    try:
        assert path.name == "cooling-failure-1.json"
        assert load_scenario(path) == c
    finally:
        path.unlink(missing_ok=True)


def test_benchmark_records_real_cpu_measurement():
    df=benchmark(default_config(),[8],3,["cpu"],repeats=2)
    row=df.iloc[0]
    assert bool(row["success"])
    assert row["compute_time_ms"] > 0
    assert row["speedup"] == pytest.approx(1)
    assert row["max_absolute_error"] == 0


def test_missing_gpu_reports_failure():
    df=benchmark(default_config(),[8],1,["cuda"],repeats=1)
    if not bool(df.iloc[0]["success"]):
        assert "CUDA" in df.iloc[0]["error"] or "cuda" in df.iloc[0]["error"]
