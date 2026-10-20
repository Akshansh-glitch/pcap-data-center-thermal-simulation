# Physical assumptions

- A cell is an effective region, not an individual measured rack. The two-dimensional field omits vertical stratification and explicit airflow.
- `ρcp`, `k`, and `h` are effective coefficients chosen for demonstration. The sample configuration is illustrative, not calibrated to a real building.
- All modeled server electrical power becomes heat in its cell. The model does not account for power supply placement or delayed heat transport.
- Cooling removes heat linearly relative to local cooling-air temperature. No chiller energy model is included, so the app does not claim an energy optimum.
- Boundary cells remain at ambient temperature. This approximates an idealized surrounding environment and may suppress temperatures near edges.
- Workload events and seeded random patterns are deterministic. A scenario is reproducible from its JSON configuration, but benchmark timing varies with hardware and load.
- A hotspot is a cell strictly above a user-selected threshold. That threshold is a study parameter, not a universal server limit.
- The model is a digital twin *prototype*. It is neither connected to live sensors nor validated to predict a commercial facility's exact temperatures.

