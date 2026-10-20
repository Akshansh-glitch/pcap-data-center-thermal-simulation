# Numerical model and units

Each interior grid cell represents an effective thermal region. Temperature `T` and cooling-air temperature `T_air` are in °C; only differences enter the energy equation. Cell width `dx` and height `dy` are in m, timestep `dt` in s, effective volumetric heat capacity `ρcp` in J/(m³·K), effective conductivity `k` in W/(m·K), cooling coefficient `h` in W/(m³·K), and volumetric source `q` in W/m³.

Utilization `U` is dimensionless in `[0,1]`. Electrical power `P = P_idle + U(P_max-P_idle)` is in W. All electrical input is assumed to become heat, `q=P/V`, for effective cell volume `V` in m³. This is a first-order approximation, not a universal server power law.

For each interior cell, the solver calculates

```
L = (T[r-1,c] - 2T[r,c] + T[r+1,c]) / dx²
  + (T[r,c-1] - 2T[r,c] + T[r,c+1]) / dy²
T_next[r,c] = T[r,c] + dt/(ρcp) × (k L + q[r,c] - h[r,c](T[r,c]-T_air[r,c]))
```

Rows follow `dx`, columns follow `dy` in the implementation. Every edge cell is set to fixed `T_ambient` each step. Two arrays ensure all updates read the previous time level. The sufficient monotonicity condition used by validation is `2kdt/(ρcp)(1/dx²+1/dy²) + h_max dt/(ρcp) ≤ 1`; it covers diffusion plus the linear cooling loss. Source values and boundary/initial discontinuities can still yield physically implausible scenarios, so users must interpret the effective parameters.

