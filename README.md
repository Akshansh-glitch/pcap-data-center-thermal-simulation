# GPU-Accelerated Data Center Thermal Simulation and Hotspot Analysis using CUDA

A simulation-based data center thermal digital twin for a Parallel Computer Architecture and Programming course. It models a two-dimensional grid of server regions, turns utilization into electrical power and heat, advances a transient heat equation, detects hotspots, compares saved scenarios, and benchmarks sequential CPU, OpenMP, CUDA global-memory, and CUDA shared-memory solvers. All charts show calculated fields. There is no live sensor feed or facility calibration.

## Current environment and verified status

The initial workspace was empty. On the development machine (Windows, 20 October 2026), Python 3.14.3, NumPy, Pandas, Plotly, Streamlit, and pytest are installed. MinGW GCC 6.3 builds and runs the sequential and OpenMP engines. Its pthread runtime DLL is present but its import library is absent, so the local build script generates that import library from the DLL exports. An NVIDIA GeForce RTX 4060 is present, but `nvcc` and CMake are unavailable on PATH. CUDA source is included but cannot be built or benchmarked here.

## Quick start on this Windows machine

```powershell
python -m pip install -r requirements.txt
.\scripts\build_mingw.ps1
python -m pytest tests -q -p no:cacheprovider
python -m streamlit run python/app.py
```

Open the local URL printed by Streamlit. The sample configuration is explicitly labelled. Start from **Thermal Twin**, step or run a batch, edit a selected cell, schedule events, then use **Scenario Lab** and **Performance Lab**. `THERMAL_ENGINE` can point to a different native executable.

Use `.\scripts\build_mingw.ps1 -SequentialOnly` if the pthread DLL is unavailable and only the reference CPU build is needed. The script requires MinGW `g++`, `objdump`, and `dlltool` on PATH for the OpenMP build. It does not modify the MinGW installation.

## CMake builds with a complete toolchain

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
ctest --test-dir build --output-on-failure
python -m pytest tests -q
python -m streamlit run python/app.py
```

CMake enables OpenMP if found. It adds the CUDA source only if a CUDA compiler is found. On Windows, CUDA requires a host compiler supported by the installed toolkit; this old MinGW compiler is not suitable. A GPU driver version shown by `nvidia-smi` is not proof that the toolkit is installed. Use the local MinGW script above on this machine; use CMake with a complete toolchain elsewhere.

## Model and architecture

The state uses row-major float32 arrays. Python generates deterministic workload and event fields; the native engine updates temperature with identical equations and fixed boundary conditions for every solver. The binary bridge passes four arrays in order: temperature, volumetric heat, cooling coefficient, and cooling-air temperature. The native process emits the next temperature field and measured timing. The UI never substitutes a CPU result for a requested GPU run.

The model is

`ρcp ∂T/∂t = k∇²T + P/V − h(T − T_air)`

with `P = P_idle + U(P_max − P_idle)`. Its explicit timestep must satisfy `2 k dt/(ρcp) (1/dx² + 1/dy²) + h_max dt/(ρcp) ≤ 1`. Boundary cells are pinned to ambient. See [equations](docs/equations.md) and [assumptions](docs/assumptions.md) for units and limitations. The 2D coefficients represent effective thermal behavior; they do not resolve detailed rack airflow.

## Features and workflow

- **Overview:** actual current field, summary metrics, and history.
- **Thermal Twin:** start/pause/resume, single step, batch, reset, selected-cell workload/cooling overrides, deterministic events, and CSV exports. The live panel advances one simulation step per refresh while running. Simulation time is `step × dt`, independent of wall time.
- **Scenario Lab:** save and reload configuration JSON; compare two or more scenarios from their own declared initial conditions over the same number of steps. For a fair study, keep initial conditions and model coefficients equal and vary only the operating strategy.
- **Performance Lab:** same initial and constant input fields for all implementations; repeated measured native compute time, process end-to-end time, kernel time, transfer time, speedup, throughput, numerical error, and CSV export. Runs are saved under `data/benchmark_results/` and reloaded as history. Missing backends appear as failed rows, not fabricated numbers.
- **Configuration:** geometry, thermal coefficients, power model, cooling, workload, hotspot threshold, and solver controls with stability validation.

The interface uses coordinate selectors for reliable cell selection. Heatmaps are downsampled only for display; metrics and exports use the full numerical grid. Large interactive grids still incur one file transfer and native process launch per dynamic step, so benchmark mode should be used for performance claims.

## Experiments and interpretation

Start with 100×100, 250×250, and 500×500 grids and 100 steps. Increase size after checking memory and run time. In the Performance Lab, repeat each experiment at least three times and export CSV. Speedup uses **native compute time** relative to the median sequential CPU time at the same size; throughput is total cell updates divided by native compute time. GPU kernel timing excludes host transfer and setup. End-to-end timing includes bridge file I/O and process startup, which matters for interactive use. OpenMP efficiency is speedup divided by thread count. Shared memory can be slower on some sizes; report the observed outcome.

Numerical validation compares the final float32 grid against sequential CPU. The default maximum absolute error tolerance is `1e-3 °C`; inspect mean and maximum error rather than treating a tolerance check as physical validation. See [experiments](docs/experiments.md) and [testing](docs/testing.md).

## Limits and future work

This is a controlled teaching prototype. It has no airflow CFD, sensor assimilation, rack geometry calibration, or validated cooling-electricity model. Scenario comparison reports thermal outcomes only. The Python subprocess protocol is reliable but adds overhead for each dynamic step. A persistent native worker or pybind11 interface would improve large-grid interaction. CUDA correctness and speedup still require a toolkit build and compatible GPU execution.

