#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ARCHITECT AI — архитектурные геномы со спиральной родословной."""

import copy
import json
import os
import random

from config import RAW_LOGS_DIR
from spiral_evolution import fingerprint_payload

try:
    from janus_genesis.agent import PARAM_RANGES
except ImportError:
    PARAM_RANGES = {
        'n_embd': [128, 256, 384, 512, 768],
        'n_head': [4, 8, 12, 16],
        'n_layer': [4, 6, 8, 10, 12]
    }


class ArchitectureGenome:
    ARCH_TYPES = [
        'transformer', 'wide_transformer', 'deep_transformer',
        'sparse_transformer', 'hybrid', 'recurrent_transformer',
        'mixture_of_experts'
    ]
    DEPTH_RANGE = (0.8, 1.5)
    WIDTH_RANGE = (0.8, 1.5)
    HEAD_RANGE = (0.8, 1.5)

    def __init__(self, arch_type=None, depth_factor=1.0, width_factor=1.0,
                 head_factor=1.0, generation=0, parent_fingerprint=None,
                 lineage=None):
        self.arch_type = arch_type if arch_type else random.choice(self.ARCH_TYPES)
        self.depth_factor = depth_factor
        self.width_factor = width_factor
        self.head_factor = head_factor
        self.generation = int(generation)
        self.parent_fingerprint = parent_fingerprint
        self.lineage = list(lineage or [])

    def _state(self):
        return {
            'arch_type': self.arch_type,
            'depth_factor': self.depth_factor,
            'width_factor': self.width_factor,
            'head_factor': self.head_factor,
            'generation': self.generation,
        }

    def mutate(self, mutation_rate=0.3, bonus=1.0):
        """Create a next-turn genome while preserving the complete ancestry."""
        parent_state = self._state()
        new_genome = copy.deepcopy(self)
        new_genome.parent_fingerprint = fingerprint_payload(parent_state)
        new_genome.generation = self.generation + 1
        new_genome.lineage = [*self.lineage, {
            'turn': self.generation,
            'fingerprint': new_genome.parent_fingerprint,
            'state': parent_state,
        }]

        effective_rate = mutation_rate * bonus
        if random.random() < effective_rate * 0.3:
            new_genome.arch_type = random.choice(self.ARCH_TYPES)

        ranges = {
            'depth_factor': self.DEPTH_RANGE,
            'width_factor': self.WIDTH_RANGE,
            'head_factor': self.HEAD_RANGE
        }
        for attr in ['depth_factor', 'width_factor', 'head_factor']:
            if random.random() < effective_rate:
                delta = random.uniform(-0.1, 0.1) * bonus
                low, high = ranges[attr]
                setattr(new_genome, attr, max(low, min(high, getattr(new_genome, attr) + delta)))
        return new_genome

    def apply_to_config(self, base_config):
        config = base_config.copy()
        base_embd = config.get('n_embd', 256)
        base_head = config.get('n_head', 8)
        base_layer = config.get('n_layer', 6)
        config['n_embd'] = int(base_embd * self.width_factor)
        config['n_head'] = int(base_head * self.head_factor)
        config['n_layer'] = int(base_layer * self.depth_factor)
        config['n_embd'] = min(PARAM_RANGES['n_embd'], key=lambda x: abs(x - config['n_embd']))
        config['n_head'] = min(PARAM_RANGES['n_head'], key=lambda x: abs(x - config['n_head']))
        config['n_layer'] = min(PARAM_RANGES['n_layer'], key=lambda x: abs(x - config['n_layer']))
        if config['n_embd'] % config['n_head'] != 0:
            possible_heads = [h for h in PARAM_RANGES['n_head'] if config['n_embd'] % h == 0]
            config['n_head'] = min(possible_heads, key=lambda x: abs(x - config['n_head'])) if possible_heads else 8
        config['arch_type'] = self.arch_type
        config['spiral_generation'] = self.generation
        return config

    def to_dict(self):
        return {
            **self._state(),
            'parent_fingerprint': self.parent_fingerprint,
            'lineage': self.lineage,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            arch_type=data['arch_type'],
            depth_factor=data['depth_factor'],
            width_factor=data['width_factor'],
            head_factor=data['head_factor'],
            generation=data.get('generation', 0),
            parent_fingerprint=data.get('parent_fingerprint'),
            lineage=data.get('lineage', []),
        )
