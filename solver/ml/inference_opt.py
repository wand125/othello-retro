# SPDX-License-Identifier: MIT
"""Opt-in, in-memory eval transforms; original modules/checkpoints stay intact.

API: optimize(net, variant), where variant is baseline, fused, channels_last,
or fused_channels_last. Call after eval()/strict checkpoint loading and before
installing diagnostic hooks. No existing inference entry point enables this.

Folding uses torch.nn.utils.fusion.fuse_conv_bn_eval. Its documented contract
requires eval mode and computed BatchNorm running buffers:
https://docs.pytorch.org/docs/stable/generated/torch.nn.utils.fuse_conv_bn_eval.html
"""
from copy import deepcopy

import torch
from torch import nn
from torch.nn.utils.fusion import fuse_conv_bn_eval

VARIANTS = ('baseline', 'fused', 'channels_last', 'fused_channels_last')


class _ChannelsLast(nn.Module):
    """Convert each input inside the measured forward, including layout cost."""
    def __init__(self, model):
        super().__init__()
        self.model = model
        self.eval()

    def forward(self, x, scalars=None):
        if self.training:
            raise RuntimeError('channels_last inference wrapper is eval-only')
        if x.ndim != 4:
            raise ValueError('expected NCHW dimensions for channels_last conversion')
        return self.model(x.contiguous(memory_format=torch.channels_last), scalars)


def _fold_sequential(module, prefix=''):
    folded = []
    for name, child in list(module.named_children()):
        path = prefix + name
        folded.extend(_fold_sequential(child, path + '.'))
    if isinstance(module, nn.Sequential):
        names = list(module._modules)
        for left, right in zip(names, names[1:]):
            conv, bn = module._modules[left], module._modules[right]
            if isinstance(conv, nn.Conv2d) and isinstance(bn, nn.BatchNorm2d):
                if bn.running_mean is None or bn.running_var is None:
                    raise ValueError('BatchNorm running buffers are required for eval folding')
                module._modules[left] = fuse_conv_bn_eval(conv, bn)
                module._modules[right] = nn.Identity()
                folded.append(prefix + left + '+' + right)
    return folded


def optimize(net, variant):
    """Return an eval-only optimized copy; baseline returns the original as-is.

    Channels-last variants convert weights and perform input layout conversion
    inside forward. This deliberately includes conversion in end-to-end timing.
    Fused state dictionaries are not interchangeable with original checkpoints;
    these copies are for inference only and are never saved by this helper.
    Floating-point reassociation can change logits/rankings: callers must check
    numerical/ranking agreement for the intended workload before deployment.
    """
    if variant not in VARIANTS:
        raise ValueError('unknown inference optimization: ' + str(variant))
    if any(module.training for module in net.modules()):
        raise ValueError('optimize requires an already-evaluating model and submodules')
    if variant == 'baseline':
        return net
    result = deepcopy(net)
    folded = _fold_sequential(result) if variant in ('fused', 'fused_channels_last') else []
    if variant in ('channels_last', 'fused_channels_last'):
        result.to(memory_format=torch.channels_last)
        result = _ChannelsLast(result)
    result.eval()
    result._inference_opt = {
        'variant': variant,
        'fused_conv_bn_pairs': len(folded),
        'folded_module_paths': folded,
        'channels_last': variant in ('channels_last', 'fused_channels_last'),
        'input_layout_conversion_in_forward': variant in ('channels_last', 'fused_channels_last'),
        'original_model_modified': False,
    }
    return result
