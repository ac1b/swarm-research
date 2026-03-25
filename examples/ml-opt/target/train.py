"""Training loop and hyperparameters."""
import random

TRAIN_CONFIG = {
    "learning_rate": 0.01,
    "hidden_size": 8,
    "epochs": 50,
    "seed": 0,
}


def train(model, data):
    """Train model on data = list of ([x1, x2], y) pairs."""
    rng = random.Random(42)
    for epoch in range(TRAIN_CONFIG["epochs"]):
        shuffled = list(data)
        rng.shuffle(shuffled)
        for x, y in shuffled:
            model.train_step(x, y)
