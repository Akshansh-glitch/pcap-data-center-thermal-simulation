import copy
import numpy as np
import pytest
from python.model import default_config, fields, initial_state, validate_config, workload
from python.engine_bridge import engine_path, run_native
from python.simulation_service import Simulation
from python.analytics import summarize


@pytest.fixture
def c():
    c = default_config()
    c.update(rows=7, cols=9, steps=4, failure_start=1000)
    c["region"] = {"row": 2, "col": 3, "height": 2, "width": 2}
    return c


def test_uniform_equilibrium(c):
    c.update(initial_temp=22, ambient=22, air_temp=22, idle_power=0, max_power=0)
    s = Simulation(c)
    s.advance(4)
    assert np.array_equal(s.temperature, initial_state(c))


def test_power_cooling_and_diffusion(c):
    c.update(conductivity=0, cooling=0, idle_power=0, max_power=0,
             initial_temp=22, ambient=22)
    t = initial_state(c)
    heat = np.zeros_like(t); heat[3,4] = 120
    cool = np.zeros_like(t); air = np.full_like(t, 18)
    hot, _ = run_native(c,t,heat,cool,air)
    assert hot[3,4] == pytest.approx(22.1, abs=1e-5)
    assert hot[3,5] == 22
    c["conductivity"] = 12
    neighbor, _ = run_native(c,hot,np.zeros_like(t),cool,air)
    assert neighbor[3,5] > 22
    assert neighbor[0,4] == c["ambient"]
    cool[3,4] = 100
    cooled, _ = run_native(c,hot,np.zeros_like(t),cool,air)
    assert cooled[3,4] < neighbor[3,4]


def test_workload_changes_heat_and_temperature(c):
    c["pattern"] = "spike"; c["spike_start"] = 1
    low = fields(c,0)[2]
    high = fields(c,1)[2]
    assert high[3,4] > low[3,4]
    s = Simulation(c)
    s.advance(3)
    baseline = dict(c, pattern="steady")
    steady = Simulation(baseline)
    steady.advance(3)
    assert s.temperature[3,4] > steady.temperature[3,4]


def test_seed_and_event_timing(c):
    c["pattern"] = "random"
    assert np.array_equal(workload(c,2),workload(c,2))
    assert not np.array_equal(workload(c,2),workload(c,3))
    c["events"] = [{"step":2,"kind":"workload","value":0.9},
                   {"step":3,"kind":"cooling","value":2.0}]
    assert not np.all(fields(c,1)[0] == .9)
    assert np.all(fields(c,2)[0] == .9)
    assert np.all(fields(c,3)[3] == 2)


def test_invalid_and_unstable(c):
    bad=copy.deepcopy(c); bad["dt"] = 100
    with pytest.raises(ValueError,match="unstable"): validate_config(bad)
    bad=copy.deepcopy(c); bad["rows"] = 0
    with pytest.raises(ValueError): validate_config(bad)
    bad=copy.deepcopy(c); bad["region"]["row"] = 99
    with pytest.raises(ValueError): validate_config(bad)


def test_cell_override_affects_next_step(c):
    a=Simulation(c); b=Simulation(c)
    b.set_cell(3,4,utilization=1,cooling=0)
    a.advance(); b.advance()
    assert b.temperature[3,4] > a.temperature[3,4]
    assert summarize(b.temperature,c["hotspot_threshold"])["hotspot_count"] >= 0


def test_openmp_matches_cpu_when_available(c):
    t=initial_state(c)
    _,_,q,h,air=fields(c,0)
    ref,_=run_native(c,t,q,h,air,4,"cpu")
    try: parallel,_=run_native(c,t,q,h,air,4,"openmp",2)
    except RuntimeError as exc: pytest.skip(str(exc))
    assert np.max(np.abs(ref-parallel)) <= 1e-5


@pytest.mark.parametrize("solver",["cuda","cuda-shared"])
def test_cuda_matches_cpu_when_available(c,solver):
    t=initial_state(c)
    _,_,q,h,air=fields(c,0)
    ref,_=run_native(c,t,q,h,air,4,"cpu")
    try: result,_=run_native(c,t,q,h,air,4,solver,block_size=64)
    except RuntimeError as exc: pytest.skip(str(exc))
    assert np.max(np.abs(ref-result)) <= 1e-3
