#include "thermal.hpp"
#include <cmath>
#include <stdexcept>
#ifdef HAVE_OPENMP
#include <omp.h>
#endif

void validate(const Model& m, const std::vector<float>& cooling) {
  if (m.rows < 1 || m.cols < 1 || m.rows > 10000 || m.cols > 10000 ||
      !std::isfinite(m.dt) || m.dt <= 0 || !std::isfinite(m.dx) || m.dx <= 0 ||
      !std::isfinite(m.dy) || m.dy <= 0 || !std::isfinite(m.rho_cp) || m.rho_cp <= 0 ||
      !std::isfinite(m.conductivity) || m.conductivity < 0 || !std::isfinite(m.ambient))
    throw std::invalid_argument("invalid geometry or physical coefficient");
  const double diffusion = double(m.conductivity) * m.dt / m.rho_cp *
      (1.0 / (double(m.dx) * m.dx) + 1.0 / (double(m.dy) * m.dy));
  if (cooling.size() != size_t(m.rows) * m.cols)
    throw std::invalid_argument("cooling size mismatch");
  float hmax = 0;
  for (float h : cooling) {
    if (!std::isfinite(h) || h < 0) throw std::invalid_argument("invalid cooling field");
    if (h > hmax) hmax = h;
  }
  // Positivity / monotonicity criterion for diffusion plus cooling loss.
  if (2.0 * diffusion + double(hmax) * m.dt / m.rho_cp > 1.0 + 1e-7)
    throw std::invalid_argument("unstable explicit timestep: reduce dt or cooling");
}

void step_cpu(const Model& m, const float* current, float* next,
              const float* heat, const float* cooling, const float* air,
              bool parallel, int threads) {
  const float cx = m.conductivity / (m.dx * m.dx);
  const float cy = m.conductivity / (m.dy * m.dy);
  const float scale = m.dt / m.rho_cp;
#ifdef HAVE_OPENMP
  if (parallel && threads > 0) omp_set_num_threads(threads);
#pragma omp parallel for if(parallel) schedule(static)
#endif
  for (int r = 0; r < m.rows; ++r) {
    for (int c = 0; c < m.cols; ++c) {
      const int i = r * m.cols + c;
      if (r == 0 || c == 0 || r == m.rows - 1 || c == m.cols - 1) {
        next[i] = m.ambient;
      } else {
        const float t = current[i];
        const float diffusion = cx * (current[i - m.cols] - 2*t + current[i + m.cols])
                              + cy * (current[i - 1] - 2*t + current[i + 1]);
        next[i] = t + scale * (diffusion + heat[i] - cooling[i] * (t - air[i]));
      }
    }
  }
}
