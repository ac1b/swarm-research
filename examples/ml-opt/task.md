---
target: [target/model.py, target/train.py]
eval: python3 eval.py
direction: maximize
rounds: 10
timeout: 45
eval_runs: 3
mode: full
backtrack: 3
max_backtracks: 3
---

# Neural Network from Scratch

Build and optimize a neural network classifier using only Python stdlib.
No numpy, sklearn, torch, or any ML libraries allowed.

## Task
Classify 2D points into 4 classes arranged in an XOR-like spiral pattern.
The dataset is non-linearly separable — a linear model cannot exceed ~50%.

## Interface
`NeuralNet` class in `model.py`:
- `__init__(self, config)` — config dict from train.py
- `forward(self, x)` — x is [x1, x2], returns list of 4 class probabilities
- `train_step(self, x, y)` — x is [x1, x2], y is int (0-3), updates weights in-place
- `parameters(self)` — returns serializable state for save/load

`TRAIN_CONFIG` dict in `train.py`:
- Must include `epochs`, `learning_rate`, and any architecture params
- `train(model, data)` — trains model on data list of (x, y) pairs

## Scoring
- 800 train / 200 test points, deterministic (seed 42)
- 4-class spiral pattern with noise (std=0.15)
- Eval trains from scratch using train.py, tests on held-out set
- Score = test accuracy * 100 (random = 25, perfect = 100)
- Banned imports detected via AST: numpy, scipy, sklearn, torch, tensorflow, jax

## Files
- `target/model.py` — network architecture, forward pass, backpropagation
- `target/train.py` — training loop, hyperparameters, learning rate schedule

## Optimization Space
- Hidden layer sizes (2-layer minimum for XOR)
- Activation functions (ReLU, tanh, sigmoid, swish)
- Weight initialization (Xavier, He, random)
- Optimizer (SGD, momentum, Adam from scratch)
- Learning rate schedule (constant, decay, warmup)
- Regularization (L2, dropout)
- Batch normalization
- Data augmentation / shuffling strategy

Baseline (2-layer net, 8 hidden, ReLU, vanilla SGD): ~65%. Well-tuned: 90%+.
