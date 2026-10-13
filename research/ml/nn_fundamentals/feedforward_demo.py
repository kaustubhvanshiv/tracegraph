"""ML-04.1: two-layer XNOR classifier, forward/loss/backward/SGD and checkpointing.

CPU-only synthetic exercise. Does not read DARPA data or establish detection metrics.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import platform

import torch
from torch import nn


class TwoLayerNet(nn.Module):
    def __init__(self, hidden=16):
        super().__init__()
        self.layers = nn.Sequential(nn.Linear(2, hidden), nn.ReLU(), nn.Linear(hidden, 1))

    def forward(self, inputs):
        return self.layers(inputs)  # [batch, 1] raw logits, not probabilities


def toy_data(seed=17, train_size=512, validation_size=256, noise=0.0):
    if train_size < 2 or validation_size < 2 or not 0 <= noise < 1:
        raise ValueError("Need at least two samples per partition and noise in [0,1)")
    generator = torch.Generator().manual_seed(seed)
    inputs = torch.rand(train_size + validation_size, 2, generator=generator) * 4 - 2
    labels = (inputs[:, :1] * inputs[:, 1:] > 0).float()
    train_x, validation_x = inputs[:train_size], inputs[train_size:]
    train_y, validation_y = labels[:train_size].clone(), labels[train_size:].clone()
    flipped = torch.rand(train_size, 1, generator=generator) < noise
    train_y[flipped] = 1 - train_y[flipped]
    # Validation is independent and clean; scaling statistics come from training.
    mean, scale = train_x.mean(0, keepdim=True), train_x.std(0, keepdim=True).clamp_min(1e-6)
    return {"train_x": (train_x - mean) / scale, "train_y": train_y,
            "validation_x": (validation_x - mean) / scale, "validation_y": validation_y,
            "mean": mean, "scale": scale, "flipped_training_labels": int(flipped.sum()),
            "train_sample_ids": list(range(train_size)),
            "validation_sample_ids": list(range(train_size, train_size + validation_size))}


def evaluate(model, inputs, labels, criterion):
    model.eval()
    with torch.no_grad():
        logits = model(inputs)
        return float(criterion(logits, labels)), float(((logits >= 0) == labels.bool()).float().mean())


def predict_from_checkpoint(path, raw_inputs):
    """Reload the saved model AND training scaler for standalone inference."""
    payload = torch.load(path, map_location="cpu", weights_only=True)
    inputs = torch.as_tensor(raw_inputs, dtype=torch.float32)
    if inputs.ndim != 2 or inputs.shape[1] != 2 or not torch.isfinite(inputs).all():
        raise ValueError("Expected finite [batch, 2] raw inputs")
    model = TwoLayerNet(payload["hidden"])
    model.load_state_dict(payload["state_dict"])
    model.eval()
    with torch.no_grad():
        return torch.sigmoid(model((inputs - payload["mean"]) / payload["scale"]))


def train(data, output, *, seed=17, hidden=16, learning_rate=.1, epochs=160, batch_size=32, weight_decay=0.0):
    if epochs < 1 or batch_size < 1 or hidden < 1 or learning_rate <= 0 or weight_decay < 0:
        raise ValueError("Invalid training configuration")
    output = Path(output)
    if output.exists():
        raise ValueError("Use a fresh output directory")
    output.mkdir(parents=True)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    model = TwoLayerNet(hidden)
    criterion = nn.BCEWithLogitsLoss()  # Applies stable sigmoid + binary cross entropy.
    optimizer = torch.optim.SGD(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    generator = torch.Generator().manual_seed(seed + 1)
    history, best_loss, first_step, stopped = [], math.inf, None, None
    checkpoint = output / "best.pt"
    best_logits = None
    for epoch in range(epochs + 1):
        if epoch:
            model.train()
            order = torch.randperm(len(data["train_x"]), generator=generator)
            for start in range(0, len(order), batch_size):
                selected = order[start:start + batch_size]
                inputs, targets = data["train_x"][selected], data["train_y"][selected]
                optimizer.zero_grad(set_to_none=True)
                logits = model(inputs)                  # forward pass
                loss = criterion(logits, targets)       # scalar loss
                if not torch.isfinite(loss):
                    stopped = f"Non-finite minibatch loss at epoch {epoch}"
                    break
                loss.backward()                        # autograd computes dL/dW
                if not all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None):
                    stopped = f"Non-finite gradient at epoch {epoch}"
                    break
                if first_step is None:
                    before = [p.detach().clone() for p in model.parameters()]
                    first_step = {"input_shape": list(inputs.shape), "target_shape": list(targets.shape),
                        "logit_shape": list(logits.shape), "loss_shape": list(loss.shape),
                        "gradient_l2": float(torch.sqrt(sum(p.grad.square().sum() for p in model.parameters())))}
                optimizer.step()                       # W <- W - lr * gradient
                if "parameter_change_l2" not in first_step:
                    first_step["parameter_change_l2"] = float(torch.sqrt(sum((p.detach() - old).square().sum() for p, old in zip(model.parameters(), before))))
            if stopped:
                break
        train_loss, train_accuracy = evaluate(model, data["train_x"], data["train_y"], criterion)
        val_loss, val_accuracy = evaluate(model, data["validation_x"], data["validation_y"], criterion)
        if not math.isfinite(train_loss) or not math.isfinite(val_loss):
            stopped = f"Non-finite evaluation loss at epoch {epoch}"
            break
        history.append({"epoch": epoch, "train_loss": train_loss, "validation_loss": val_loss,
                        "train_accuracy": train_accuracy, "validation_accuracy": val_accuracy})
        if val_loss < best_loss:
            best_loss = val_loss
            with torch.no_grad():
                best_logits = model(data["validation_x"]).clone()
            # Serialize immediately; do not keep an aliased mutable state_dict.
            torch.save({"state_dict": model.state_dict(), "hidden": hidden, "epoch": epoch,
                        "validation_loss": val_loss, "mean": data["mean"], "scale": data["scale"]}, checkpoint)
    if not history:
        raise ValueError("No finite evaluation available")
    payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
    restored = TwoLayerNet(payload["hidden"])
    restored.load_state_dict(payload["state_dict"])
    restored.eval()
    with torch.no_grad():
        restored_logits = restored(data["validation_x"])
    torch.testing.assert_close(restored_logits, best_logits, rtol=0, atol=0)
    result = {"scope": "synthetic XNOR exercise only; not security detection", "seed": seed,
        "python": platform.python_version(), "torch": torch.__version__, "device": "cpu",
        "configuration": {"hidden": hidden, "learning_rate": learning_rate, "epochs": epochs,
                          "batch_size": batch_size, "weight_decay": weight_decay},
        "train_size": len(data["train_x"]), "validation_size": len(data["validation_x"]),
        "flipped_training_labels": data["flipped_training_labels"], "first_step": first_step,
        "best_epoch": payload["epoch"], "best_validation_loss": payload["validation_loss"],
        "checkpoint_reload_max_abs_difference": float((restored_logits - best_logits).abs().max()),
        "stopped_reason": stopped, "history": history}
    (output / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def plot_demo(result, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    history = result["history"]
    figure, axis = plt.subplots(figsize=(8, 4.5), constrained_layout=True)
    axis.plot([r["epoch"] for r in history], [r["train_loss"] for r in history], label="Training BCE")
    axis.plot([r["epoch"] for r in history], [r["validation_loss"] for r in history], label="Validation BCE")
    axis.axvline(result["best_epoch"], color="#666666", linestyle=":", label="Best validation checkpoint")
    axis.set(xlabel="Epoch", ylabel="Binary cross entropy", title="Two-layer network on synthetic XNOR (CPU)")
    axis.legend()
    axis.grid(alpha=.2)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".cache/ml-runs/feedforward-demo"))
    parser.add_argument("--epochs", type=int, default=160)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    result = train(toy_data(args.seed), args.output, seed=args.seed, epochs=args.epochs)
    plot_demo(result, args.output / "learning_curves.png")
    print(json.dumps({k: v for k, v in result.items() if k != "history"}, indent=2))


if __name__ == "__main__":
    main()
