# Validation status and commands

On the initial Windows machine, the executable was compiled using MinGW GCC 6.3 and `scripts/build_mingw.ps1`. The script generated an import library from the installed pthread runtime DLL so OpenMP could link without modifying the toolchain. `python -m pytest tests -q -p no:cacheprovider` reported **10 passed, 2 skipped**. The skipped tests cover CUDA global and shared variants because `nvcc` is unavailable. They must be rerun after a compatible CUDA build. The CMake smoke test was not run because CMake is not installed.

The tests cover uniform equilibrium, localized heat and neighbor diffusion, cooling response, boundary pinning, workload spike response, seeded random determinism, event timing, invalid configurations and timestep stability, selected-cell overrides, scenario JSON roundtrip, measured CPU benchmark fields, and honest GPU failure reporting. They compare available parallel solvers against the sequential final grid. Intermediate-state comparisons and CUDA tile/block edge cases should be added when a CUDA build is available.

Run:

```bash
python -m pytest tests -q -p no:cacheprovider
ctest --test-dir build --output-on-failure
```

The native engine validates its own timestep and arrays as well as the Python layer. A successful numerical comparison establishes implementation agreement, not physical accuracy.

A measured example run using 100 timesteps, four OpenMP threads, and three repeats is saved in `data/benchmark_results/`. Sequential CPU median compute time was 7.8102 ms at 100×100, 40.7564 ms at 250×250, and 179.2895 ms at 500×500. OpenMP median compute time was 9.4330, 25.0189, and 67.0423 ms respectively, with final-grid maximum absolute error 0.0 °C. CUDA rows explicitly record the missing build. These numbers are observations from this machine, not portable performance claims.
