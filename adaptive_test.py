#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adaptive Test — проверяет, насколько сложную среду может осилить модель.
Повышает сложность, пока loss не превысит порог, но не более максимальной сложности.
"""

import torch
import torch.nn.functional as F
import numpy as np
import random
from config import VOCAB_SIZE

def make_hierarchical_dataset(num_sequences, seq_len, vocab_size,
                              hidden_states, contexts, meta_contexts,
                              intra_cluster_prob, switch_prob,
                              seed=42, device='cpu'):
    """
    Генерирует последовательности со сменой скрытых состояний.
    Каждое скрытое состояние владеет своим кластером токенов.
    Возвращает список тензоров формы [seq_len] (без batch).
    """
    torch.manual_seed(seed)
    random.seed(seed)
    np.random.seed(seed)

    cluster_size = vocab_size // hidden_states
    clusters = []
    for h in range(hidden_states):
        start = h * cluster_size
        end = start + cluster_size if h < hidden_states - 1 else vocab_size
        clusters.append(list(range(start, end)))

    trans = []
    for h in range(hidden_states):
        current_cluster = clusters[h]
        len_current = len(current_cluster)
        len_other = vocab_size - len_current

        P = np.zeros((vocab_size, vocab_size))
        prob_in = intra_cluster_prob / len_current
        prob_out = (1 - intra_cluster_prob) / len_other if len_other > 0 else 0

        for prev in range(vocab_size):
            for nxt in range(vocab_size):
                if nxt in current_cluster:
                    P[prev, nxt] = prob_in
                else:
                    P[prev, nxt] = prob_out
        P = P / P.sum(axis=1, keepdims=True)
        trans.append(P)

    data = []
    for _ in range(num_sequences):
        h = np.random.randint(0, hidden_states)
        tokens = [np.random.choice(vocab_size, p=trans[h][0])]
        for pos in range(1, seq_len):
            if np.random.random() < switch_prob:
                h = np.random.randint(0, hidden_states)
            nxt_tok = np.random.choice(vocab_size, p=trans[h][tokens[-1]])
            tokens.append(nxt_tok)
        data.append(torch.tensor(tokens, device=device))
    return data


async def adaptive_test(model, gain, temperature, base_seed=1000, threshold=5.0, device='cpu'):
    """
    Возвращает максимальную достигнутую сложность (целое число) и последний loss.
    Если достигнута максимальная сложность, останавливается.
    """
    model.eval()
    seq_len = 64
    hidden_states = 4
    contexts = 2
    meta_contexts = 1
    intra_cluster_prob = 0.8
    switch_prob = 0.1

    max_hidden = 20
    max_contexts = 8
    max_meta = 4
    max_seq_len = 128

    complexity = 0
    with torch.no_grad():
        while True:
            # Генерируем тестовые данные с текущей сложностью
            test_data = make_hierarchical_dataset(
                num_sequences=50,
                seq_len=seq_len,
                vocab_size=VOCAB_SIZE,
                hidden_states=hidden_states,
                contexts=contexts,
                meta_contexts=meta_contexts,
                intra_cluster_prob=intra_cluster_prob,
                switch_prob=switch_prob,
                seed=base_seed + complexity,
                device='cpu'
            )
            total_loss = 0.0
            count = 0
            for seq in test_data:
                seq = seq.to(device)
                # Добавляем batch-измерение, если его нет
                if seq.dim() == 1:
                    seq = seq.unsqueeze(0)  # [1, seq_len]
                logits = model(seq)          # [1, seq_len, vocab]
                # Берём все позиции кроме последней для предсказания следующего токена
                shift_logits = logits[:, :-1, :].reshape(-1, VOCAB_SIZE)  # [(seq_len-1), vocab]
                shift_labels = seq[:, 1:].reshape(-1)                     # [seq_len-1]
                shift_logits_scaled = shift_logits * gain
                shift_logits_temp = shift_logits_scaled / temperature
                loss = F.cross_entropy(shift_logits_temp, shift_labels)
                total_loss += loss.item()
                count += 1
            avg_loss = total_loss / count if count > 0 else 1e6

            # Если loss превысил порог, останавливаемся
            if avg_loss > threshold:
                break

            # Проверяем, достигли ли мы максимальной сложности
            if (seq_len >= max_seq_len and 
                hidden_states >= max_hidden and 
                contexts >= max_contexts and 
                meta_contexts >= max_meta):
                # Достигли максимума, но loss всё ещё ниже порога – останавливаемся
                break

            # Увеличиваем сложность
            complexity += 1
            if complexity % 5 == 0:
                seq_len = min(max_seq_len, seq_len + 16)
            if complexity % 3 == 0:
                hidden_states = min(max_hidden, hidden_states + 1)
            if complexity % 4 == 0:
                contexts = min(max_contexts, contexts + 1)
            if complexity % 6 == 0:
                meta_contexts = min(max_meta, meta_contexts + 1)
            if complexity % 2 == 0:
                intra_cluster_prob = max(0.3, intra_cluster_prob - 0.05)
            if complexity % 2 == 0:
                switch_prob = min(0.8, switch_prob + 0.05)

    return complexity, avg_loss