# GPU-Accelerated Matrix Operations

This folder contains a concise notebook comparing NumPy and CuPy for matrix operations on CPU and GPU. It highlights runtime differences, memory-transfer overhead, and the point where GPU acceleration becomes useful.

## Install

Use the CUDA 13 wheel for this machine:

`pip install "cupy-cuda13x[ctk]"`

If CUDA is not installed, the notebook still runs the NumPy path and skips the GPU path.

## Contents

- `gpu_matrix_ops.ipynb`: short walkthrough and benchmark scaffold
- CPU path: NumPy matrix operations
- GPU path: CuPy matrix operations
- Notes on batching, parallel execution, and overhead tradeoffs

## Summary

The main takeaway is that GPU acceleration helps most on larger workloads or repeated batches. For smaller inputs, CPU vectorization can be faster once transfer overhead is included.
