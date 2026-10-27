// =============================================================================
//  Data Center Hotspot Simulation with CUDA
// =============================================================================
//  The server room floor is a grid of N x N cells. Every cell has a temperature.
//  Every second (one "step"), each cell:
//     + gets warmer, because its servers produce heat
//     - gets cooler, because the air conditioner (AC) blows cold air
//     ~ shares heat with its 4 neighbours (hot cells warm up cooler ones)
//
//  In one part of the room the AC is broken, so that area overheats.
//  A cell above 30 C is called a HOTSPOT.
//
//  We run the same simulation twice and compare the speed:
//     CPU: one cell after another, in a loop
//     GPU: one CUDA thread per cell, all cells at the same time
//
//  Compile (RTX 50 series):  nvcc -O2 -arch=sm_120 -o thermal_sim thermal_sim.cu
//  Run:                      thermal_sim
// =============================================================================

#include <cuda_runtime.h>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <vector>

// --------------------------------- Settings ----------------------------------
constexpr int   STEPS     = 500;     // simulate 500 seconds
constexpr float START     = 22.0f;   // starting temperature of every cell (C)
constexpr float WALL      = 22.0f;   // the room's walls always stay at 22 C
constexpr float AIR       = 18.0f;   // temperature of the cold air from the AC (C)
constexpr float HEAT      = 0.05f;   // servers warm each cell by 0.05 C per second
constexpr float AC_OK     = 0.01f;   // cooling strength where the AC works
constexpr float AC_BROKEN = 0.001f;  // cooling strength where the AC is broken
constexpr float SPREAD    = 0.1f;    // how quickly heat moves between neighbours
constexpr float HOTSPOT   = 30.0f;   // above this temperature = hotspot (C)

// -----------------------------------------------------------------------------
//  The rule for ONE cell. Used by both the CPU and the GPU, so both compute
//  exactly the same thing. (__host__ = can run on CPU, __device__ = on GPU)
// -----------------------------------------------------------------------------
__host__ __device__ float new_temperature(float me, float up, float down,
                                          float left, float right, float ac) {
  float spreading = SPREAD * (up + down + left + right - 4.0f * me);  // towards neighbours
  float cooling   = ac * (me - AIR);                                  // AC pulls towards 18 C
  return me + HEAT - cooling + spreading;
}

// =============================================================================
//  CPU version: visit every cell, one after another.
// =============================================================================
void simulate_cpu(std::vector<float>& T, const std::vector<float>& ac, int N) {
  std::vector<float> T_new(N * N);
  for (int step = 0; step < STEPS; step++) {
    for (int row = 0; row < N; row++) {
      for (int col = 0; col < N; col++) {
        int i = row * N + col;
        if (row == 0 || col == 0 || row == N - 1 || col == N - 1)
          T_new[i] = WALL;
        else
          T_new[i] = new_temperature(T[i], T[i - N], T[i + N], T[i - 1], T[i + 1], ac[i]);
      }
    }
    T.swap(T_new);  // the new temperatures become the input for the next second
  }
}

// =============================================================================
//  GPU version: this function (a "kernel") runs on the GPU. We start one thread
//  per cell, and every thread updates only its own cell. There is no loop over
//  the cells: the thousands of threads replace the CPU's two for-loops.
// =============================================================================
__global__ void step_gpu(const float* T, float* T_new, const float* ac, int N) {
  int col = blockIdx.x * blockDim.x + threadIdx.x;  // which cell is mine?
  int row = blockIdx.y * blockDim.y + threadIdx.y;
  if (row >= N || col >= N) return;                 // spare thread outside the room

  int i = row * N + col;
  if (row == 0 || col == 0 || row == N - 1 || col == N - 1)
    T_new[i] = WALL;
  else
    T_new[i] = new_temperature(T[i], T[i - N], T[i + N], T[i - 1], T[i + 1], ac[i]);
}

void check(cudaError_t result) {
  if (result != cudaSuccess) {
    printf("CUDA error: %s\n", cudaGetErrorString(result));
    exit(1);
  }
}

// =============================================================================
//  Runs the whole simulation on the GPU. Three stages:
//     1. copy the data from the CPU's memory to the GPU's memory
//     2. launch the kernel once per second of simulated time
//     3. copy the final temperatures back to the CPU
// =============================================================================
void simulate_gpu(std::vector<float>& T, const std::vector<float>& ac, int N) {
  size_t bytes = N * N * sizeof(float);
  float *gpu_T, *gpu_T_new, *gpu_ac;               // pointers to GPU memory
  check(cudaMalloc(&gpu_T, bytes));
  check(cudaMalloc(&gpu_T_new, bytes));
  check(cudaMalloc(&gpu_ac, bytes));

  // 1. CPU -> GPU
  check(cudaMemcpy(gpu_T, T.data(), bytes, cudaMemcpyHostToDevice));
  check(cudaMemcpy(gpu_ac, ac.data(), bytes, cudaMemcpyHostToDevice));

  // 2. Each block is 16 x 16 = 256 threads. We need enough blocks to cover the
  //    whole N x N room (rounded up, so the edges are covered too).
  dim3 threads(16, 16);
  dim3 blocks((N + 15) / 16, (N + 15) / 16);
  for (int step = 0; step < STEPS; step++) {
    step_gpu<<<blocks, threads>>>(gpu_T, gpu_T_new, gpu_ac, N);
    float* temp = gpu_T; gpu_T = gpu_T_new; gpu_T_new = temp;  // swap, like the CPU
  }
  check(cudaGetLastError());

  // 3. GPU -> CPU (this also waits until the GPU has finished all steps)
  check(cudaMemcpy(T.data(), gpu_T, bytes, cudaMemcpyDeviceToHost));

  cudaFree(gpu_T);
  cudaFree(gpu_T_new);
  cudaFree(gpu_ac);
}

// The AC strength of every cell. The AC is broken in one square of the room.
std::vector<float> build_room(int N) {
  std::vector<float> ac(N * N, AC_OK);
  for (int row = N / 4; row < N / 2; row++)
    for (int col = N / 4; col < N / 2; col++)
      ac[row * N + col] = AC_BROKEN;
  return ac;
}

double now_ms() {
  auto t = std::chrono::steady_clock::now().time_since_epoch();
  return std::chrono::duration<double, std::milli>(t).count();
}

// Print a small picture of the room. Each character shows one sample cell.
void print_map(const std::vector<float>& T, int N) {
  const int ROWS = 24, COLS = 48;
  printf("\nRoom after %d seconds (%d x %d grid, shown as %d x %d characters)\n", STEPS, N, N, ROWS, COLS);
  printf("   .  normal (below 25 C)     +  warm (25-30 C)     #  HOTSPOT (above 30 C)\n\n");
  for (int r = 0; r < ROWS; r++) {
    printf("   ");
    for (int c = 0; c < COLS; c++) {
      float t = T[(r * N / ROWS) * N + (c * N / COLS)];
      printf("%c", t > HOTSPOT ? '#' : (t > 25.0f ? '+' : '.'));
    }
    printf("\n");
  }
}

int main() {
  cudaDeviceProp gpu;
  check(cudaGetDeviceProperties(&gpu, 0));
  printf("GPU: %s\n", gpu.name);

  // Warm-up: the very first GPU run includes one-time start-up work.
  // Run a tiny simulation once so that this cost is not counted in the timings.
  std::vector<float> tiny(16 * 16, START);
  simulate_gpu(tiny, build_room(16), 16);

  printf("\nSimulating %d seconds of a data center with a broken AC unit\n\n", STEPS);
  printf("%-13s %10s %10s %9s %10s %12s\n", "Grid", "CPU (ms)", "GPU (ms)", "Speedup", "Hotspots", "Same result?");

  std::vector<float> final_room;
  int final_N = 0;
  int sizes[] = {256, 512, 1024, 2048};

  for (int N : sizes) {
    std::vector<float> ac = build_room(N);
    std::vector<float> T_cpu(N * N, START);
    std::vector<float> T_gpu(N * N, START);

    double t0 = now_ms();
    simulate_cpu(T_cpu, ac, N);
    double t1 = now_ms();
    simulate_gpu(T_gpu, ac, N);
    double t2 = now_ms();

    // Compare the CPU and GPU answers, and count the hotspots.
    float biggest_difference = 0.0f;
    int hotspots = 0;
    for (int i = 0; i < N * N; i++) {
      biggest_difference = fmaxf(biggest_difference, fabsf(T_cpu[i] - T_gpu[i]));
      if (T_gpu[i] > HOTSPOT) hotspots++;
    }

    char grid[32];
    snprintf(grid, sizeof(grid), "%d x %d", N, N);
    printf("%-13s %10.1f %10.1f %8.1fx %10d %12s\n", grid, t1 - t0, t2 - t1,
           (t1 - t0) / (t2 - t1), hotspots, biggest_difference < 0.001f ? "yes" : "NO");

    final_room = T_gpu;
    final_N = N;
  }

  print_map(final_room, final_N);
  return 0;
}
