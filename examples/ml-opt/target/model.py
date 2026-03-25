"""Neural network classifier. No external libraries allowed."""
import math
import random


class NeuralNet:
    """Simple 2-layer network. Baseline ~60% on spiral — room to improve."""

    def __init__(self, config):
        self.lr = config.get("learning_rate", 0.01)
        hidden = config.get("hidden_size", 8)
        random.seed(config.get("seed", 0))

        # Layer 1: 2 -> hidden
        self.W1 = [[random.gauss(0, 0.5) for _ in range(2)] for _ in range(hidden)]
        self.b1 = [0.0] * hidden
        # Layer 2: hidden -> 4
        self.W2 = [[random.gauss(0, 0.5) for _ in range(hidden)] for _ in range(4)]
        self.b2 = [0.0] * 4
        self.hidden = hidden

    def _relu(self, x):
        return max(0.0, x)

    def _softmax(self, logits):
        max_l = max(logits)
        exps = [math.exp(l - max_l) for l in logits]
        s = sum(exps)
        return [e / s for e in exps]

    def forward(self, x):
        """Forward pass. x = [x1, x2]. Returns list of 4 probabilities."""
        # Hidden layer
        self._h_pre = [sum(self.W1[h][j] * x[j] for j in range(2)) + self.b1[h]
                       for h in range(self.hidden)]
        self._h = [self._relu(v) for v in self._h_pre]
        # Output layer
        logits = [sum(self.W2[c][h] * self._h[h] for h in range(self.hidden)) + self.b2[c]
                  for c in range(4)]
        self._last_x = x
        self._last_probs = self._softmax(logits)
        return self._last_probs

    def train_step(self, x, y):
        """One gradient step with backprop. x = [x1, x2], y = class (0-3)."""
        probs = self.forward(x)

        # Output gradient: dL/d_logit = prob - one_hot
        d_logits = [probs[c] - (1.0 if c == y else 0.0) for c in range(4)]

        # Backprop through output layer
        d_hidden = [0.0] * self.hidden
        for c in range(4):
            for h in range(self.hidden):
                d_hidden[h] += d_logits[c] * self.W2[c][h]
        # Update W2 after computing d_hidden
        for c in range(4):
            for h in range(self.hidden):
                self.W2[c][h] -= self.lr * d_logits[c] * self._h[h]
            self.b2[c] -= self.lr * d_logits[c]

        # ReLU backward
        d_h_pre = [d_hidden[h] * (1.0 if self._h_pre[h] > 0 else 0.0)
                   for h in range(self.hidden)]

        # W1 gradients
        for h in range(self.hidden):
            for j in range(2):
                self.W1[h][j] -= self.lr * d_h_pre[h] * self._last_x[j]
            self.b1[h] -= self.lr * d_h_pre[h]

    def parameters(self):
        return {"W1": self.W1, "b1": self.b1, "W2": self.W2, "b2": self.b2}
