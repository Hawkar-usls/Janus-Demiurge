#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARCHITECT AI — управляет архитектурными геномами.
Позволяет мутировать тип модели и структурные параметры.
"""

import random
import copy
import json
import os
from config import RAW_LOGS_DIR

class ArchitectureGenome:
    """
    Геном архитектуры нейросети.
    Содержит тип модели и факторы, влияющие на конфигурацию.
    """
    
    # Новые архитектурные типы
    ARCH_TYPES = [
        'transformer',
        'wide_transformer',
        'deep_transformer',
        'sparse_transformer',
        'hybrid',
        'recurrent_transformer',    # <-- NEW
        'mixture_of_experts'         # <-- NEW
    ]
    
    DEPTH_RANGE = (0.8, 1.5)
    WIDTH_RANGE = (0.8, 1.5)
    HEAD_RANGE = (0.8, 1.5)
    
    def __init__(self, arch_type=None, depth_factor=1.0, width_factor=1.0, head_factor=1.0):
        self.arch_type = arch_type if arch_type else random.choice(self.ARCH_TYPES)
        self.depth_factor = depth_factor
        self.width_factor = width_factor
        self.head_factor = head_factor
    
    def mutate(self, mutation_rate=0.3, bonus=1.0):
        """
        Мутирует геном. 
        bonus — дополнительный множитель для вероятности мутации (например, от артефактов).
        """
        effective_rate = mutation_rate * bonus
        new_genome = copy.deepcopy(self)
        
        if random.random() < effective_rate * 0.3:
            new_genome.arch_type = random.choice(self.ARCH_TYPES)
        
        ranges = {
            'depth_factor': self.DEPTH_RANGE,
            'width_factor': self.WIDTH_RANGE,
            'head_factor': self.HEAD_RANGE
        }
        
        for attr in ['depth_factor', 'width_factor', 'head_factor']:
            if random.random() < effective_rate:
                delta = random.uniform(-0.1, 0.1) * bonus  # усиление дельты
                new_val = getattr(new_genome, attr) + delta
                low, high = ranges[attr]
                new_val = max(low, min(high, new_val))
                setattr(new_genome, attr, new_val)
        
        return new_genome
    
    def apply_to_config(self, base_config):
        config = base_config.copy()
        base_embd = config.get('n_embd', 256)
        base_head = config.get('n_head', 8)
        base_layer = config.get('n_layer', 6)
        
        config['n_embd'] = int(base_embd * self.width_factor)
        config['n_head'] = int(base_head * self.head_factor)
        config['n_layer'] = int(base_layer * self.depth_factor)
        
        if config['n_embd'] % config['n_head'] != 0:
            for nh in [4, 8, 12, 16]:
                if config['n_embd'] % nh == 0:
                    config['n_head'] = nh
                    break
            else:
                config['n_head'] = 8
        
        config['arch_type'] = self.arch_type
        return config
    
    def to_dict(self):
        return {
            'arch_type': self.arch_type,
            'depth_factor': self.depth_factor,
            'width_factor': self.width_factor,
            'head_factor': self.head_factor
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            arch_type=data['arch_type'],
            depth_factor=data['depth_factor'],
            width_factor=data['width_factor'],
            head_factor=data['head_factor']
        )