#include "thermal.hpp"
#include <cuda_runtime.h>
#include <stdexcept>
#include <string>
#include <vector>

static void check(cudaError_t e) {
  if (e != cudaSuccess) throw std::runtime_error(cudaGetErrorString(e));
}

__global__ void global_step(Model m, const float* src, float* dst,
                            const float* heat, const float* cool, const float* air) {
  const int c = blockIdx.x * blockDim.x + threadIdx.x;
  const int r = blockIdx.y * blockDim.y + threadIdx.y;
  if (r >= m.rows || c >= m.cols) return;
  const int i = r * m.cols + c;
  if (!r || !c || r == m.rows - 1 || c == m.cols - 1) { dst[i] = m.ambient; return; }
  const float t = src[i];
  const float lap = m.conductivity * ((src[i-m.cols]-2*t+src[i+m.cols])/(m.dx*m.dx)
                                      +(src[i-1]-2*t+src[i+1])/(m.dy*m.dy));
  dst[i] = t + m.dt / m.rho_cp * (lap + heat[i] - cool[i]*(t-air[i]));
}

__global__ void shared_step(Model m, const float* src, float* dst,
                            const float* heat, const float* cool, const float* air) {
  extern __shared__ float tile[];
  const int width = blockDim.x + 2, height = blockDim.y + 2;
  const int lane = threadIdx.y * blockDim.x + threadIdx.x;
  const int count = blockDim.x * blockDim.y;
  for (int j = lane; j < width * height; j += count) {
    const int rr = blockIdx.y * blockDim.y + j / width - 1;
    const int cc = blockIdx.x * blockDim.x + j % width - 1;
    tile[j] = (rr >= 0 && cc >= 0 && rr < m.rows && cc < m.cols)
      ? src[rr*m.cols+cc] : m.ambient;
  }
  __syncthreads();
  const int r = blockIdx.y * blockDim.y + threadIdx.y;
  const int c = blockIdx.x * blockDim.x + threadIdx.x;
  if (r >= m.rows || c >= m.cols) return;
  const int i = r*m.cols+c;
  if (!r || !c || r == m.rows-1 || c == m.cols-1) { dst[i] = m.ambient; return; }
  const int center = (threadIdx.y+1)*width + threadIdx.x+1;
  const float t = tile[center];
  const float lap = m.conductivity * ((tile[center-width]-2*t+tile[center+width])/(m.dx*m.dx)
                                      +(tile[center-1]-2*t+tile[center+1])/(m.dy*m.dy));
  dst[i] = t + m.dt/m.rho_cp*(lap+heat[i]-cool[i]*(t-air[i]));
}

GpuResult run_cuda(const Model& m, const std::vector<float>& initial,
                   const std::vector<float>& heat, const std::vector<float>& cooling,
                   const std::vector<float>& air, int steps, bool shared,
                   int block_size, std::vector<float>& output) {
  int count = 0; check(cudaGetDeviceCount(&count));
  if (!count) throw std::runtime_error("no CUDA device available");
  cudaDeviceProp prop{}; check(cudaGetDeviceProperties(&prop, 0));
  if (block_size < 1 || block_size > prop.maxThreadsPerBlock)
    throw std::invalid_argument("unsupported CUDA block size");
  const int bx = block_size >= 256 ? 16 : (block_size >= 64 ? 8 : 4);
  const int by = block_size / bx;
  if (bx*by != block_size || bx > prop.maxThreadsDim[0] || by > prop.maxThreadsDim[1])
    throw std::invalid_argument("block size must be a supported multiple of 4");
  const size_t tile_bytes = size_t(bx+2)*(by+2)*sizeof(float);
  if (shared && tile_bytes > prop.sharedMemPerBlock)
    throw std::invalid_argument("tile exceeds device shared memory");
  const size_t bytes = initial.size()*sizeof(float);
  float *a=nullptr,*b=nullptr,*q=nullptr,*h=nullptr,*air_d=nullptr;
  cudaEvent_t e0=nullptr,e1=nullptr,e2=nullptr,e3=nullptr,e4=nullptr;
  try {
    check(cudaMalloc(&a, bytes)); check(cudaMalloc(&b, bytes));
    check(cudaMalloc(&q, bytes)); check(cudaMalloc(&h, bytes)); check(cudaMalloc(&air_d, bytes));
    check(cudaEventCreate(&e0)); check(cudaEventCreate(&e1));
    check(cudaEventCreate(&e2)); check(cudaEventCreate(&e3)); check(cudaEventCreate(&e4));
    check(cudaEventRecord(e0));
    check(cudaMemcpy(a, initial.data(), bytes, cudaMemcpyHostToDevice));
    check(cudaMemcpy(q, heat.data(), bytes, cudaMemcpyHostToDevice));
    check(cudaMemcpy(h, cooling.data(), bytes, cudaMemcpyHostToDevice));
    check(cudaMemcpy(air_d, air.data(), bytes, cudaMemcpyHostToDevice));
    check(cudaEventRecord(e1));
    check(cudaEventRecord(e2));
    const dim3 block(bx,by), grid((m.cols+bx-1)/bx,(m.rows+by-1)/by);
    for (int s=0;s<steps;++s) {
      if (shared) shared_step<<<grid,block,tile_bytes>>>(m,a,b,q,h,air_d);
      else global_step<<<grid,block>>>(m,a,b,q,h,air_d);
      check(cudaGetLastError());
      float* tmp=a; a=b; b=tmp;
    }
    check(cudaEventRecord(e3)); check(cudaEventSynchronize(e3));
    check(cudaMemcpy(output.data(),a,bytes,cudaMemcpyDeviceToHost));
    check(cudaEventRecord(e4)); check(cudaEventSynchronize(e4));
    float upload=0, download=0, kernel=0;
    check(cudaEventElapsedTime(&upload,e0,e1));
    check(cudaEventElapsedTime(&download,e3,e4));
    check(cudaEventElapsedTime(&kernel,e2,e3));
    GpuResult result{kernel,upload+download,prop.name};
    cudaEventDestroy(e0); cudaEventDestroy(e1); cudaEventDestroy(e2); cudaEventDestroy(e3); cudaEventDestroy(e4);
    cudaFree(a); cudaFree(b); cudaFree(q); cudaFree(h); cudaFree(air_d);
    return result;
  } catch (...) {
    if (e0) cudaEventDestroy(e0); if (e1) cudaEventDestroy(e1);
    if (e2) cudaEventDestroy(e2); if (e3) cudaEventDestroy(e3);
    if (e4) cudaEventDestroy(e4);
    if (a) cudaFree(a); if (b) cudaFree(b); if (q) cudaFree(q);
    if (h) cudaFree(h); if (air_d) cudaFree(air_d);
    throw;
  }
}
