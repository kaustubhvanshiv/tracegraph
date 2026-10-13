"""ML-04.2: controlled learning-rate, overfitting and weight-decay experiments."""
import argparse
import json
from pathlib import Path

from research.ml.nn_fundamentals.feedforward_demo import toy_data, train


def experiment(output, seed=17):
    output = Path(output)
    if output.exists():
        raise ValueError("Use a fresh output directory")
    output.mkdir(parents=True)
    clean = toy_data(seed, train_size=320, validation_size=256)
    noisy = toy_data(seed, train_size=32, validation_size=256, noise=.3)
    cases = {"lr_low": (clean, {"learning_rate": .0001, "epochs": 120}),
             "lr_appropriate": (clean, {"learning_rate": .1, "epochs": 120}),
             "lr_high": (clean, {"learning_rate": 20., "epochs": 120}),
             "small_unregularized": (noisy, {"hidden": 128, "learning_rate": .2, "epochs": 1500, "weight_decay": 0}),
             "small_weight_decay": (noisy, {"hidden": 128, "learning_rate": .2, "epochs": 1500, "weight_decay": .02})}
    results = {}
    for name, (data, settings) in cases.items():
        results[name] = train(data, output / name, seed=seed, **settings)
        result = results[name]
        print(f"{name}: best val BCE {result['best_validation_loss']:.4f}, final val BCE {result['history'][-1]['validation_loss']:.4f}", flush=True)
    plot(results, output / "training_dynamics.png")
    summary = {name: {k: value for k, value in result.items() if k != "history"} | {"initial": result["history"][0], "final": result["history"][-1]} for name, result in results.items()}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def plot(results, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figure, axes = plt.subplots(1, 2, figsize=(13, 4.8), constrained_layout=True)
    names = ["lr_low", "lr_appropriate", "lr_high"]
    colors = ["#7c3aed", "#0f766e", "#c2410c"]
    for name, color in zip(names, colors):
        history = results[name]["history"]
        label = f"lr={results[name]['configuration']['learning_rate']:g}"
        axes[0].plot([r["epoch"] for r in history], [r["validation_loss"] for r in history], color=color, label=label + " validation")
        axes[0].plot([r["epoch"] for r in history], [r["train_loss"] for r in history], color=color, linestyle="--", alpha=.65)
    axes[0].set(title="Learning rate: solid validation, dashed training", xlabel="Epoch", ylabel="BCE loss (log scale)", yscale="log")
    for name, color, label in [("small_unregularized", "#c2410c", "No regularization"), ("small_weight_decay", "#0f766e", "Weight decay 0.02")]:
        history = results[name]["history"]
        axes[1].plot([r["epoch"] for r in history], [r["validation_loss"] for r in history], color=color, label=label + " validation")
        axes[1].plot([r["epoch"] for r in history], [r["train_loss"] for r in history], color=color, linestyle="--", label=label + " training")
    axes[1].set(title="Overfitting: 32 training samples with label noise", xlabel="Epoch", ylabel="BCE loss")
    for axis in axes:
        axis.legend(fontsize=8)
        axis.grid(alpha=.2)
    figure.suptitle("Synthetic XNOR training dynamics — no DARPA data", fontsize=13)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".cache/ml-runs/training-dynamics"))
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    experiment(args.output, args.seed)


if __name__ == "__main__":
    main()
