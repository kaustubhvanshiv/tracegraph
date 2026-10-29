"""Small vector autoencoder for the separately approved label-free pilot."""
import hashlib
import json
import math

import torch
from torch import nn


class ActivityAutoencoder(nn.Module):
    def __init__(self, input_dim=62, hidden_dim=16, latent_dim=4):
        super().__init__()
        self.layers = nn.Sequential(nn.Linear(input_dim,hidden_dim),nn.ReLU(),
            nn.Linear(hidden_dim,latent_dim),nn.Linear(latent_dim,hidden_dim),
            nn.ReLU(),nn.Linear(hidden_dim,input_dim))

    def forward(self, values):
        return self.layers(values)


def state_digest(model):
    payload = {name:dict(dtype=str(t.dtype),shape=list(t.shape),values=t.detach().cpu().tolist())
               for name,t in sorted(model.state_dict().items())}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def reconstruction_metrics(model, values):
    model.eval()
    with torch.inference_mode():
        residual = model(values)-values
        return residual_metrics(residual)


def baseline_metrics(baseline, values):
    return residual_metrics(values-baseline)


def residual_metrics(residual):
    mse,mae = torch.stack((residual.square().mean(),residual.abs().mean())).detach().cpu().tolist()
    if not math.isfinite(mse) or not math.isfinite(mae):
        raise ValueError('Nonfinite reconstruction metric')
    return dict(mse=mse,mae=mae)
