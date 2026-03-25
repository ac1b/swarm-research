"""Neural network evaluator. Trains from scratch, tests on held-out spiral data."""
import ast
import importlib.util
import math
import random
import sys
import os

# ── Banned import check ───────────────────────────────────────────────

BANNED = {"numpy", "np", "scipy", "sklearn", "torch", "tensorflow", "tf",
          "jax", "paddle", "mxnet", "keras", "onnx", "cupy"}


def check_banned_imports(filepath):
    with open(filepath) as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in BANNED:
                    return alias.name
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in BANNED:
                return node.module
    return None


# ── Dataset: 4-class spiral ───────────────────────────────────────────

def make_spiral_data(n_points, noise_std, seed):
    """Generate 4-class spiral dataset in 2D."""
    rng = random.Random(seed)
    data = []
    n_per_class = n_points // 4
    for cls in range(4):
        for i in range(n_per_class):
            t = i / n_per_class * 2.0 * math.pi * 0.75  # 0 to 3/4 turn
            r = 0.3 + t / (2.0 * math.pi)  # radius grows with angle
            angle = t + cls * math.pi / 2  # offset each class by 90 degrees
            x = r * math.cos(angle) + rng.gauss(0, noise_std)
            y = r * math.sin(angle) + rng.gauss(0, noise_std)
            data.append(([x, y], cls))
    # Shuffle deterministically
    rng.shuffle(data)
    return data


# ── Evaluation ────────────────────────────────────────────────────────

def evaluate():
    # Check for banned imports
    for fpath in ["target/model.py", "target/train.py"]:
        banned = check_banned_imports(fpath)
        if banned:
            print(f"SCORE: 0", flush=True)
            return

    # Load modules
    try:
        for name, path in [("train", "target/train.py")]:
            s = importlib.util.spec_from_file_location(name, path)
            m = importlib.util.module_from_spec(s)
            sys.modules[name] = m
            s.loader.exec_module(m)

        spec = importlib.util.spec_from_file_location("model", "target/model.py")
        model_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(model_mod)
        train_mod = sys.modules["train"]
    except Exception as e:
        print(f"SCORE: 0", flush=True)
        return

    # Generate data
    all_data = make_spiral_data(1000, noise_std=0.15, seed=42)
    train_data = all_data[:800]
    test_data = all_data[800:]

    # Train
    try:
        config = train_mod.TRAIN_CONFIG
        model = model_mod.NeuralNet(config)
        train_mod.train(model, train_data)
    except Exception as e:
        print(f"SCORE: 0", flush=True)
        return

    # Test
    try:
        correct = 0
        for x, y in test_data:
            probs = model.forward(x)
            pred = max(range(len(probs)), key=lambda i: probs[i])
            if pred == y:
                correct += 1
        accuracy = correct / len(test_data) * 100
    except Exception as e:
        print(f"SCORE: 0", flush=True)
        return

    print(f"SCORE: {accuracy:.2f}", flush=True)


if __name__ == "__main__":
    evaluate()
