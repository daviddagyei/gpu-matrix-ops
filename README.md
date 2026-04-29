# GPU-Accelerated Synthetic Classification and Matrix Workloads

This repository contains a single notebook that compares NumPy and CuPy on two complementary workloads: synthetic matrix-heavy benchmarks and a synthetic Gaussian-mixture classification problem. It is meant to show both GPU programming performance and ML evaluation in one place.

## Install

Use the CUDA 13 wheel for this machine:

`pip install "cupy-cuda13x[ctk]"`

If CUDA is not installed, the notebook still runs the NumPy path and skips the GPU path.

## Notebook Sections

- Matrix multiply examples with small concrete inputs
- Synthetic square-matrix sweeps with compute-only and end-to-end GPU timing
- Synthetic linear-layer benchmarks that resemble ML inference kernels
- Batched GEMM benchmarks for larger GPU-friendly workloads
- Synthetic classification from Gaussian distributions
- Softmax regression training on NumPy and CuPy
- Accuracy, macro precision, macro recall, macro F1, and confusion matrices
- Plots for runtime, loss curves, class scatter, and confusion matrices

## What To Look For

- GPU speedups are easier to see on larger matrices, larger batch sizes, and batched linear algebra.
- End-to-end GPU timing is the honest comparison because it includes data transfer.
- The classification section shows that the notebook is not only about speed, but also about model quality and evaluation.
