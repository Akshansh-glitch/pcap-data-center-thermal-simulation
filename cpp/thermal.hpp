#pragma once
#include <vector>
#include <string>

struct Model {
  int rows, cols;
  float dt, dx, dy, rho_cp, conductivity, ambient;
};

void validate(const Model& m, const std::vector<float>& cooling);
void step_cpu(const Model& m, const float* current, float* next,
              const float* heat, const float* cooling, const float* air,
              bool parallel, int threads);
#ifdef HAVE_CUDA
struct GpuResult { double kernel_ms, transfer_ms; std::string device; };
GpuResult run_cuda(const Model& m, const std::vector<float>& initial,
                   const std::vector<float>& heat, const std::vector<float>& cooling,
                   const std::vector<float>& air, int steps, bool shared,
                   int block_size, std::vector<float>& output);
#endif
