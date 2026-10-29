"""Explicit CPU/CUDA placement and deterministic runtime setup."""
import os
import random

import torch


def configure_runtime(config):
    device = torch.device(config['device'])
    if device.type == 'cuda':
        workspace = config.get('cublas_workspace_config')
        if workspace not in (':4096:8',':16:8'):
            raise ValueError('CUDA runs need an explicit deterministic cuBLAS workspace')
        os.environ['CUBLAS_WORKSPACE_CONFIG'] = workspace
        if not torch.cuda.is_available():
            raise ValueError('CUDA was requested but no compatible CUDA runtime/GPU is available')
        torch.set_float32_matmul_precision(config.get('matmul_precision','highest'))
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        torch.cuda.manual_seed_all(config['seed'])
        torch.cuda.reset_peak_memory_stats(device)
    random.seed(config['seed']);torch.manual_seed(config['seed'])
    torch.set_num_threads(config['cpu_threads']);torch.use_deterministic_algorithms(True)
    return device


def synchronize(device):
    if device.type == 'cuda':
        torch.cuda.synchronize(device)


def runtime_details(device):
    if device.type != 'cuda':
        return dict(device_name='CPU',compiled_cuda=torch.version.cuda)
    props = torch.cuda.get_device_properties(device)
    return dict(device_name=props.name,compiled_cuda=torch.version.cuda,
        compute_capability=[props.major,props.minor],total_vram_bytes=props.total_memory,
        peak_allocated_bytes=torch.cuda.max_memory_allocated(device),
        peak_reserved_bytes=torch.cuda.max_memory_reserved(device),
        matmul_precision=torch.get_float32_matmul_precision(),
        cublas_workspace_config=os.environ['CUBLAS_WORKSPACE_CONFIG'])


def all_finite(tensors):
    tensors = [t.reshape(-1) for t in tensors if t is not None]
    return not tensors or bool(torch.isfinite(torch.cat(tensors)).all())
