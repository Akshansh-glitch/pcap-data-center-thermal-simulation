#include "thermal.hpp"
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#ifdef _WIN32
#include <windows.h>
#endif

static double now_ms() {
#ifdef _WIN32
  LARGE_INTEGER counter, frequency;
  QueryPerformanceCounter(&counter); QueryPerformanceFrequency(&frequency);
  return 1000.0 * double(counter.QuadPart) / double(frequency.QuadPart);
#else
  return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now().time_since_epoch()).count();
#endif
}

static std::vector<float> read_array(std::ifstream& f, size_t n) {
  std::vector<float> v(n);
  f.read(reinterpret_cast<char*>(v.data()), n * sizeof(float));
  if (!f) throw std::runtime_error("input file is incomplete");
  return v;
}

int main(int argc, char** argv) {
  if (argc == 2 && std::string(argv[1]) == "--help") {
    std::cout << "thermal_engine input.bin output.bin rows cols steps dt dx dy rho_cp conductivity ambient cpu|openmp|cuda|cuda-shared threads block_size\n";
    return 0;
  }
  try {
    if (argc != 16) throw std::invalid_argument("expected 15 arguments; use --help");
    const Model m{std::stoi(argv[3]), std::stoi(argv[4]), std::stof(argv[6]),
                  std::stof(argv[7]), std::stof(argv[8]), std::stof(argv[9]),
                  std::stof(argv[10]), std::stof(argv[11])};
    const int steps = std::stoi(argv[5]);
    const std::string solver = argv[12];
    const int threads = std::stoi(argv[13]);
    const int block_size = std::stoi(argv[14]);
    // Last argument is a reserved protocol version, preventing accidental mismatch.
    if (std::string(argv[15]) != "v1" || steps < 1 || steps > 1000000)
      throw std::invalid_argument("invalid step count or protocol version");
    const size_t n = size_t(m.rows) * m.cols;
    if (n > 100000000) throw std::invalid_argument("grid exceeds 100 million cells");
    std::ifstream f(argv[1], std::ios::binary);
    if (!f) throw std::runtime_error("cannot open input file");
    auto current = read_array(f, n);
    auto heat = read_array(f, n);
    auto cooling = read_array(f, n);
    auto air = read_array(f, n);
    validate(m, cooling);
    for (float t : current) if (!std::isfinite(t)) throw std::invalid_argument("invalid temperature field");
    for (float q : heat) if (!std::isfinite(q) || q < 0) throw std::invalid_argument("invalid heat field");
    for (float a : air) if (!std::isfinite(a)) throw std::invalid_argument("invalid air field");
    const double start = now_ms();
    double kernel_ms = 0, transfer_ms = 0;
    std::string device;
    if (solver == "cpu" || solver == "openmp") {
#ifndef HAVE_OPENMP
      if (solver == "openmp") throw std::runtime_error("OpenMP was not enabled at build time");
#endif
      std::vector<float> next(n);
      for (int step = 0; step < steps; ++step) {
        step_cpu(m, current.data(), next.data(), heat.data(), cooling.data(), air.data(), solver == "openmp", threads);
        current.swap(next);
      }
    } else if (solver == "cuda" || solver == "cuda-shared") {
#ifdef HAVE_CUDA
      auto result = run_cuda(m, current, heat, cooling, air, steps, solver == "cuda-shared", block_size, current);
      kernel_ms = result.kernel_ms; transfer_ms = result.transfer_ms; device = result.device;
#else
      throw std::runtime_error("CUDA support was not built: install CUDA toolkit and rebuild");
#endif
    } else throw std::invalid_argument("unknown solver");
    const double end = now_ms();
    std::ofstream out(argv[2], std::ios::binary);
    if (!out) throw std::runtime_error("cannot open output file");
    out.write(reinterpret_cast<const char*>(current.data()), n * sizeof(float));
    if (!out) throw std::runtime_error("cannot write output file");
    const double compute_ms = end-start;
    std::cout << std::fixed << std::setprecision(6)
              << "compute_ms=" << compute_ms << "\nkernel_ms=" << kernel_ms
              << "\ntransfer_ms=" << transfer_ms << "\ndevice=" << device << '\n';
    return 0;
  } catch (const std::exception& e) {
    std::cerr << "error: " << e.what() << '\n';
    return 2;
  }
}
