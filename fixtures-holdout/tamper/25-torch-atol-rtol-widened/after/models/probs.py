import torch


def softmax_temp(logits, temp=1.0):
    return torch.softmax(logits / temp, dim=-1)


def entropy(p):
    return -(p * torch.log(p.clamp_min(1e-12))).sum(dim=-1)
