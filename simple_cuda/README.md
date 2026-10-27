# Data Center Hotspot Simulation with CUDA

**The whole project is one file: `thermal_sim.cu`.**

## The idea in 30 seconds

- A server room floor is divided into a grid of cells. Every cell has a temperature.
- Every second, each cell gets **warmer** from its servers, **cooler** from the AC, and **shares heat** with its 4 neighbours.
- In one part of the room **the AC is broken**, so that area overheats. Any cell above **30 °C** is a **hotspot**.
- We run the same simulation on the **CPU** (one cell at a time) and on the **GPU** (one thread per cell, all at once), then compare the speed.

## The rule for one cell

```
new = old + HEAT − AC × (old − 18) + SPREAD × (up + down + left + right − 4 × old)
            servers   air conditioner          heat moving between neighbours
```

| Setting | Value | Meaning |
|---|---|---|
| `HEAT` | 0.05 | servers add 0.05 °C every second |
| `AC_OK` | 0.01 | working AC: normal cells settle at about 23 °C |
| `AC_BROKEN` | 0.001 | broken AC: cells keep heating up |
| `SPREAD` | 0.1 | how fast heat moves to neighbours |
| `WALL` | 22 | the edges of the room always stay at 22 °C |

A cell's new temperature depends only on **its own old value and its 4 neighbours' old values**. So every cell can be computed **at the same time**. That's why a GPU helps.

## The code, function by function

| Function | Runs on | What it does |
|---|---|---|
| `new_temperature` | CPU and GPU | The rule above for one cell |
| `simulate_cpu` | CPU | Two `for` loops visit every cell, repeated 500 times |
| `step_gpu` | **GPU** | **The CUDA kernel.** Each thread works out its own row/column and updates one cell |
| `simulate_gpu` | CPU, controls the GPU | `cudaMalloc` → `cudaMemcpy` to GPU → launch the kernel 500 times → `cudaMemcpy` back |
| `build_room` | CPU | Marks where the AC is broken |
| `main` | CPU | Runs both versions for 4 grid sizes, prints the table and the room map |

### How a GPU thread finds its cell

```cpp
int col = blockIdx.x * blockDim.x + threadIdx.x;
int row = blockIdx.y * blockDim.y + threadIdx.y;
```

Threads are grouped in **blocks of 16 × 16 = 256**. For example, thread (5, 3) in block (2, 1) gets:
column = 2 × 16 + 5 = **37**, row = 1 × 16 + 3 = **19**.
For a 1024 × 1024 room the program launches 64 × 64 blocks × 256 threads = **1,048,576 threads**, one per cell.

### Why there are two temperature arrays

Each step **reads** the old temperatures and **writes** into a second array. If threads wrote into the same array, a thread could read a neighbour that has already been updated, and the result would be wrong. After each step the two arrays are swapped. Only the pointers swap; no data is copied.

## How to run on the RTX 5050 laptop (Windows)

Install these once:
1. **NVIDIA driver**, the latest from nvidia.com.
2. **Visual Studio Community** with the **"Desktop development with C++"** workload. The CUDA compiler needs Microsoft's C++ compiler.
3. **CUDA Toolkit 12.8 or newer**. The RTX 50 series needs at least 12.8.

Then open **"x64 Native Tools Command Prompt for VS"** from the Start menu, go to this folder, and run:

```
nvcc -O2 -arch=sm_120 -o thermal_sim.exe thermal_sim.cu
thermal_sim.exe
```

`sm_120` is the code name of the RTX 50 series architecture. On a different GPU, use `-arch=native` instead.

## How to run on Google Colab (no install needed)

Upload `thermal_sim_colab.ipynb` with **File → Upload notebook**. Pick **Runtime → Change runtime type → T4 GPU**, then **Runtime → Run all**.

## What the output looks like

The numbers below are an illustration. Your times will differ.

```
GPU: NVIDIA GeForce RTX 5050 Laptop GPU

Simulating 500 seconds of a data center with a broken AC unit

Grid            CPU (ms)   GPU (ms)   Speedup   Hotspots Same result?
256 x 256           ...        ...      ...x        ...          yes
512 x 512           ...        ...      ...x        ...          yes
1024 x 1024         ...        ...      ...x        ...          yes
2048 x 2048         ...        ...      ...x        ...          yes

Room after 500 seconds (2048 x 2048 grid, shown as 24 x 48 characters)
   .  normal (below 25 C)     +  warm (25-30 C)     #  HOTSPOT (above 30 C)

   ................................................
   ............++++++++++++++......................
   ............+############+......................
   ...
```

- **GPU (ms)** includes copying the data to and from the GPU, so the comparison is fair.
- **Same result? = yes** means the GPU's answer matches the CPU's to within 0.001 °C, so the GPU is correct.
- **The speedup grows with the grid size.** Small grids don't give the GPU enough work to keep its thousands of cores busy.
