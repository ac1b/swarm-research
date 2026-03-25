"""Numerical integration eval.

Score = avg(correct_significant_digits) * 10 across test integrals.
Each integral has a known exact value. Budget: 100 function evaluations.
"""
import importlib, math, sys

sys.path.insert(0, "target")
if "integrator" in sys.modules:
    mod = importlib.reload(sys.modules["integrator"])
else:
    mod = importlib.import_module("integrator")

N_POINTS = 100

# (function, a, b, exact_value, description)
test_cases = [
    (lambda x: x ** 2, 0, 1, 1 / 3,
     "polynomial x^2"),
    (lambda x: math.sin(x), 0, math.pi, 2.0,
     "sin(x) over [0, pi]"),
    (lambda x: math.exp(-x * x), -2, 2, math.sqrt(math.pi) * math.erf(2),
     "Gaussian e^(-x^2)"),
    (lambda x: 1 / (1 + x * x), 0, 1, math.pi / 4,
     "arctan integrand"),
    (lambda x: math.sqrt(x + 1e-15), 0.0, 1.0, 2 / 3,
     "sqrt(x), singular derivative at 0"),
    (lambda x: math.sin(x) ** 2, 0, 2 * math.pi, math.pi,
     "sin^2(x), oscillatory"),
    (lambda x: 1 / (1 + 25 * x * x), -1, 1, 2 * math.atan(5) / 5,
     "Runge function, sharp peak"),
]

total_digits = 0.0
for func, a, b, exact, desc in test_cases:
    try:
        result = mod.integrate(func, a, b, N_POINTS)
    except Exception:
        print("SCORE: 0", flush=True)
        sys.exit(0)

    if not isinstance(result, (int, float)) or math.isnan(result) or math.isinf(result):
        print("SCORE: 0", flush=True)
        sys.exit(0)

    # Correct significant digits = -log10(relative error)
    if exact == 0:
        error = abs(result)
        digits = -math.log10(error + 1e-15)
    else:
        rel_error = abs(result - exact) / abs(exact)
        digits = -math.log10(rel_error + 1e-15)

    # Cap at 14 (double precision limit)
    digits = max(0, min(digits, 14))
    total_digits += digits

score = (total_digits / len(test_cases)) * 10
print(f"SCORE: {score:.2f}", flush=True)
