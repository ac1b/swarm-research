"""Neural network classifier. No external libraries allowed."""
import math
import random


class NeuralNet:
    """Single neuron (logistic regression). Cannot solve XOR — needs hidden layers."""

    def __init__(self, config):
        self.lr = config.get("learning_rate", 0.01)
        # Single output layer: 2 inputs -> 4 classes
        random.seed(config.get("seed", 0))
        self.W = [[random.gauss(0, 0.1) for _ in range(2)] for _ in range(4)]
        self.b = [0.0] * 4

    def forward(self, x):
        """Forward pass. x = [x1, x2]. Returns list of 4 probabilities."""
        logits = [sum(self.W[c][j] * x[j] for j in range(2)) + self.b[c]
                  for c in range(4)]
        # Softmax
        max_l = max(logits)
        exps = [math.exp(l - max_l) for l in logits]
        s = sum(exps)
        return [e / s for e in exps]

    def train_step(self, x, y):
        """One gradient step. x = [x1, x2], y = class index (0-3)."""
        probs = self.forward(x)
        # Cross-entropy gradient: dL/d_logit = prob - one_hot
        for c in range(4):
            grad = probs[c] - (1.0 if c == y else 0.0)
            for j in range(2):
                self.W[c][j] -= self.lr * grad * x[j]
            self.b[c] -= self.lr * grad

    def parameters(self):
        return {"W": self.W, "b": self.b}
