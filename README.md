# GPU-Accelerated Matrix Operations

This repository contains a concise notebook comparing NumPy and CuPy for matrix operations on CPU and GPU, plus a synthetic classification workload. It highlights runtime differences, memory-transfer overhead, model quality, and the point where GPU acceleration becomes useful.

## Install

Use the CUDA 13 wheel for this machine:

`pip install "cupy-cuda13x[ctk]"`

If CUDA is not installed, the notebook still runs the NumPy path and skips the GPU path.

## Contents

- `gpu_matrix_ops.ipynb`: walkthrough, benchmark suite, and synthetic classification example
- CPU path: NumPy matrix operations
- GPU path: CuPy matrix operations
- Notes on batching, parallel execution, and overhead tradeoffs

## Summary

The main takeaway is that GPU acceleration helps most on larger workloads or repeated batches, especially when data can stay resident on the device. For smaller inputs, CPU vectorization can be faster once transfer overhead is included.
