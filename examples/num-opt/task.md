---
target: target/integrator.py
eval: python3 eval.py
direction: maximize
rounds: 10
backtrack: 3
max_backtracks: 3
timeout: 30
---
Optimize the numerical integration algorithm for maximum accuracy.

**Problem:** Compute definite integrals using at most `n_points` function evaluations.

**Goal:** Maximize the number of correct significant digits across 7 test integrals
(polynomial, trigonometric, Gaussian, oscillatory, singular, sharp peak).

**Rules:**
- Function signature: `integrate(f, a, b, n_points) -> float`
- Use at most `n_points` calls to `f` (budget = 100)
- Python stdlib only (math module OK), no numpy/scipy
- Must handle diverse function shapes

**Scoring:** avg(correct_digits) * 10. Left Riemann sum ~ 15-20. Perfect (14 digits) = 140.

**Approaches to explore:** Midpoint rule, trapezoidal rule, Simpson's rule,
Gaussian quadrature (Gauss-Legendre), adaptive subdivision, Romberg integration.
