# Reproducible experiment guide

1. Record OS, compiler version, CPU model, GPU model, CUDA toolkit and driver versions, and build options.
2. Keep one configuration fixed. Test 100², 250², 500², and 1000² cells for 100 steps; add larger sizes only when memory and runtime permit.
3. Use a steady workload for core solver scaling. All solvers receive identical temperature, heat, cooling, and cooling-air arrays.
4. Warm up parallel solvers, run at least three measured repeats, export the Performance Lab CSV, and report median with observed variability.
5. Compare CPU vs OpenMP thread counts and CUDA global vs shared kernels. Record `compute_time_ms` for speedup and `kernel_time_ms` separately for kernel analysis.
6. Inspect `max_absolute_error`, `mean_absolute_error`, and `within_tolerance` for every parallel result. A failed CUDA row means no measured GPU result.
7. For thermal strategy comparison, save a baseline and alternatives with equal grid, initial temperature, model parameters, and horizon. Change only workload/cooling inputs and report peak, mean, hotspot count, and timeline.

`compute_time_ms` includes the native solver call (CUDA allocation and transfers for GPU) but excludes bridge file I/O and process startup. `end_to_end_time_ms` includes those costs. `transfer_time_ms` includes host-to-device plus device-to-host copies. `throughput = rows × cols × steps / (compute_time_ms / 1000)`. OpenMP efficiency is CPU speedup divided by OpenMP thread count. No benchmark CSV is shipped with invented results.

