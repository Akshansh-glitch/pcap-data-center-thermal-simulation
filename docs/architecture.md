# Architecture

```text
Streamlit UI ── Python scenario/configuration services
                     │
                     ├─ deterministic workload + event generator
                     ├─ power → volumetric heat fields
                     ├─ full-grid analytics and CSV exports
                     └─ binary subprocess bridge
                              │
                         thermal_engine
                          ├─ sequential C++
                          ├─ OpenMP C++ (optional build)
                          ├─ CUDA global memory (optional build)
                          └─ CUDA shared tile (optional build)
```

The bridge writes four contiguous float32 arrays and passes dimensions, physical coefficients, solver, and step count as command arguments. The native engine validates inputs and returns a float32 temperature array plus timings. For dynamic interaction, Python generates new fields and runs one native step at a time. For steady-input benchmarks, one native process runs many steps without per-step host transfer. CUDA arrays stay on device for the benchmark's inner loop. A separate state object holds temperature, overrides, step count, and actual history. UI reruns do not recompute a completed simulation.

Scheduled event step numbers are zero-based update indices. An event at step 100 changes inputs before the update that takes the state from step 100 to step 101. Cell overrides use the same timing.

