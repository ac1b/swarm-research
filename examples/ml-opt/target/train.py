"""Training loop and hyperparameters."""

TRAIN_CONFIG = {
    "learning_rate": 0.01,
    "epochs": 50,
    "seed": 0,
}


def train(model, data):
    """Train model on data = list of ([x1, x2], y) pairs."""
    for epoch in range(TRAIN_CONFIG["epochs"]):
        for x, y in data:
            model.train_step(x, y)
