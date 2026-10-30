import torch

from models.probs import entropy, softmax_temp


def test_softmax_rows_sum_to_one():
    p = softmax_temp(torch.randn(8, 5), temp=0.7)
    assert torch.allclose(p.sum(-1), torch.ones(8), atol=1e-2)


def test_uniform_entropy():
    p = torch.full((1, 4), 0.25)
    torch.testing.assert_close(entropy(p), torch.tensor([1.3862944]), rtol=1e-1, atol=1e-1)
