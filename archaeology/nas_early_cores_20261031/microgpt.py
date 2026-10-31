# -*- coding: utf-8 -*-
"""
MicroGPT NAS Edition
- pure Python autograd
- lightweight autoregressive transformer
- slime trace + quantization support
- safe import/export for PC -> NAS handoff
- metrics tokenization for NAS / beacon / eye streams
"""

import json
import math
import os
import pickle
import random
from collections import deque

import numpy as np

try:
    from config import (
        VOCAB_PATH,
        ACTIVE_QUANTIZED_JSON,
        ACTIVE_MODEL_META_JSON,
        DEFAULT_IMPORT_QUANT_MODE,
    )
except Exception:
    from config import VOCAB_PATH
    ACTIVE_QUANTIZED_JSON = "microgpt_quantized_state.json"
    ACTIVE_MODEL_META_JSON = "microgpt_active_meta.json"
    DEFAULT_IMPORT_QUANT_MODE = "int8"


def _atomic_pickle_write(path, payload):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    temp_path = path + ".tmp"
    try:
        with open(temp_path, "wb") as handle:
            pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def _atomic_json_write(path, payload):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    temp_path = path + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def _dict_or_empty(value):
    if isinstance(value, dict):
        return dict(value)
    return {}


IMPORT_WEIGHT_NAME_ALIASES = {
    "wte.weight": "wte",
    "wpe.weight": "wpe",
    "lm_head.weight": "lm_head",
}


def _normalize_import_weight_name(name):
    raw_name = str(name or "").strip()
    if not raw_name:
        return ""
    return IMPORT_WEIGHT_NAME_ALIASES.get(raw_name, raw_name)


def _build_model_config_mismatch(incoming_model_config, runtime_model_config):
    mismatch = {}
    for key, runtime_value in runtime_model_config.items():
        if key not in incoming_model_config:
            continue
        incoming_value = incoming_model_config.get(key)
        if incoming_value != runtime_value:
            mismatch[key] = {
                "incoming": incoming_value,
                "runtime": runtime_value,
            }
    return mismatch


# =========================================================
# 1. VALUE / AUTOGRAD
# =========================================================
class Value:
    __slots__ = ("data", "grad", "_children", "_local_grads")

    def __init__(self, data, children=(), local_grads=()):
        self.data = float(data)
        self.grad = 0.0
        self._children = children
        self._local_grads = local_grads

    def __add__(self, other):
        other = other if isinstance(other, Value) else Value(other)
        return Value(self.data + other.data, (self, other), (1.0, 1.0))

    def __mul__(self, other):
        other = other if isinstance(other, Value) else Value(other)
        return Value(self.data * other.data, (self, other), (other.data, self.data))

    def __pow__(self, other):
        return Value(self.data ** other, (self,), (other * (self.data ** (other - 1)),))

    def log(self):
        safe = self.data if self.data > 1e-15 else 1e-15
        return Value(math.log(safe), (self,), (1.0 / safe,))

    def exp(self):
        x = self.data
        if x > 60.0:
            x = 60.0
        elif x < -60.0:
            x = -60.0
        e = math.exp(x)
        return Value(e, (self,), (e,))

    def relu(self):
        return Value(max(0.0, self.data), (self,), (1.0 if self.data > 0.0 else 0.0,))

    def tanh(self):
        t = math.tanh(self.data)
        return Value(t, (self,), (1.0 - t * t,))

    def __neg__(self):
        return self * -1.0

    def __radd__(self, other):
        return self + other

    def __sub__(self, other):
        return self + (-other)

    def __rsub__(self, other):
        return other + (-self)

    def __rmul__(self, other):
        return self * other

    def __truediv__(self, other):
        return self * (other ** -1)

    def backward(self):
        topo = []
        visited = set()
        stack = [(self, 0)]

        while stack:
            node, state = stack.pop()
            if state == 0:
                if node in visited:
                    continue
                visited.add(node)
                stack.append((node, 1))
                for child in node._children:
                    stack.append((child, 0))
            else:
                topo.append(node)

        self.grad = 1.0
        for node in reversed(topo):
            for child, local_grad in zip(node._children, node._local_grads):
                child.grad += local_grad * node.grad


# =========================================================
# 2. MICRO GPT
# =========================================================
class MicroGPT:
    def __init__(self, vocab_size, n_layer=1, n_embd=16, block_size=16, n_head=4, seed=None):
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        self.vocab_size = max(int(vocab_size), 2)
        self.n_layer = max(1, int(n_layer))
        self.n_embd = max(4, int(n_embd))
        self.block_size = max(4, int(block_size))
        self.n_head = max(1, int(n_head))

        if self.n_embd % self.n_head != 0:
            self.n_head = 1

        self.head_dim = self.n_embd // self.n_head

        self.char_to_id = {}
        self.id_to_char = {}
        self._load_vocab()

        self.state_dict = {}
        self._build_base_weights()

        self.params = []
        self.grad_history = deque(maxlen=512)
        self.loss_history = deque(maxlen=512)
        self.quant_history = deque(maxlen=64)
        self.slime_trace = {}
        self.slime_threshold = 0.30
        self.dna = {
            "mlp_hidden_mult": 4,
            "n_head": self.n_head,
            "quant_mode": "float",
            "quant_bits_default": 8,
        }

        self._refresh_params(init_missing_trace=True)

    # -----------------------------------------------------
    # init helpers
    # -----------------------------------------------------
    def _matrix(self, nout, nin, std=0.08):
        return [[Value(random.gauss(0.0, std)) for _ in range(nin)] for _ in range(nout)]

    def _build_base_weights(self):
        self.state_dict = {
            "wte": self._matrix(self.vocab_size, self.n_embd),
            "wpe": self._matrix(self.block_size, self.n_embd),
            "lm_head": self._matrix(self.vocab_size, self.n_embd),
        }

        for layer_idx in range(self.n_layer):
            self.state_dict["layer{0}.attn_wq".format(layer_idx)] = self._matrix(self.n_embd, self.n_embd)
            self.state_dict["layer{0}.attn_wk".format(layer_idx)] = self._matrix(self.n_embd, self.n_embd)
            self.state_dict["layer{0}.attn_wv".format(layer_idx)] = self._matrix(self.n_embd, self.n_embd)
            self.state_dict["layer{0}.attn_wo".format(layer_idx)] = self._matrix(self.n_embd, self.n_embd)
            self.state_dict["layer{0}.mlp_fc1".format(layer_idx)] = self._matrix(4 * self.n_embd, self.n_embd)
            self.state_dict["layer{0}.mlp_fc2".format(layer_idx)] = self._matrix(self.n_embd, 4 * self.n_embd)

    def _refresh_params(self, init_missing_trace=False):
        self.params = [param for matrix in self.state_dict.values() for row in matrix for param in row]
        if init_missing_trace:
            for p in self.params:
                if id(p) not in self.slime_trace:
                    self.slime_trace[id(p)] = 1.0

    def _load_vocab(self):
        try:
            with open(VOCAB_PATH, "r", encoding="utf-8") as handle:
                vocab_list = json.load(handle)
            if isinstance(vocab_list, list) and vocab_list:
                self.char_to_id = {}
                self.id_to_char = {}
                for i, token in enumerate(vocab_list):
                    token = str(token)
                    self.char_to_id[token] = i
                    self.id_to_char[i] = token
        except Exception:
            self.char_to_id = {}
            self.id_to_char = {}

        if not self.char_to_id:
            chars = list(
                "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,!?;:-_()[]{}<>/\\\"'\n\t"
                "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
                "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
            )
            self.char_to_id = {}
            self.id_to_char = {}
            for i, ch in enumerate(chars):
                self.char_to_id[ch] = i
                self.id_to_char[i] = ch

        for special in ("<UNK>", "<BOS>", "<EOS>"):
            if special not in self.char_to_id:
                idx = len(self.char_to_id)
                self.char_to_id[special] = idx
                self.id_to_char[idx] = special

        self.vocab_size = len(self.char_to_id)

    # -----------------------------------------------------
    # math blocks
    # -----------------------------------------------------
    def linear(self, x, w):
        return [sum(weight * value for weight, value in zip(row, x)) for row in w]

    def softmax(self, logits):
        max_val = max(item.data if isinstance(item, Value) else item for item in logits)
        exps = []
        for item in logits:
            shifted = item - max_val if isinstance(item, Value) else item - max_val
            exps.append(shifted.exp() if isinstance(shifted, Value) else math.exp(shifted))
        total = sum(item.data if isinstance(item, Value) else item for item in exps)
        if total <= 0.0:
            total = 1e-12
        return [item / total for item in exps]

    def rmsnorm(self, x):
        mean_square = sum((item.data if isinstance(item, Value) else item) ** 2 for item in x) / max(1, len(x))
        scale = (mean_square + 1e-5) ** -0.5
        return [item * scale for item in x]

    # -----------------------------------------------------
    # slime helpers
    # -----------------------------------------------------
    def oxytocin_bond(self, error_value):
        ev = abs(float(error_value))
        if ev > 20.0:
            ev = 20.0
        return math.exp(-ev)

    def update_slime_trace(self, param, bond):
        pid = id(param)
        old = self.slime_trace.get(pid, 1.0)
        self.slime_trace[pid] = 0.9 * old + 0.1 * float(bond)

    def piston_push(self, grad_norm):
        self.grad_history.append(float(grad_norm))

    def structural_cleanup(self):
        removed = 0
        for _, matrix in self.state_dict.items():
            for row in matrix:
                for p in row:
                    bond = self.slime_trace.get(id(p), 1.0)
                    if bond < self.slime_threshold:
                        p.data = 0.0
                        removed += 1
        return removed

    # -----------------------------------------------------
    # forward / train / eval / generation
    # -----------------------------------------------------
    def forward(self, token_id, pos_id, keys, values):
        safe_token = int(token_id) % self.vocab_size
        safe_pos = int(pos_id) % self.block_size

        x = self.rmsnorm(
            [
                token_emb + pos_emb
                for token_emb, pos_emb in zip(
                    self.state_dict["wte"][safe_token],
                    self.state_dict["wpe"][safe_pos],
                )
            ]
        )

        for layer_idx in range(self.n_layer):
            residual = x
            x = self.rmsnorm(x)

            q = self.linear(x, self.state_dict["layer{0}.attn_wq".format(layer_idx)])
            k = self.linear(x, self.state_dict["layer{0}.attn_wk".format(layer_idx)])
            v = self.linear(x, self.state_dict["layer{0}.attn_wv".format(layer_idx)])

            keys[layer_idx].append(k)
            values[layer_idx].append(v)

            attended = []
            for head in range(self.n_head):
                head_start = head * self.head_dim

                q_head = q[head_start: head_start + self.head_dim]
                k_head = [item[head_start: head_start + self.head_dim] for item in keys[layer_idx]]
                v_head = [item[head_start: head_start + self.head_dim] for item in values[layer_idx]]

                logits = []
                for t in range(len(k_head)):
                    score = sum(q_head[j] * k_head[t][j] for j in range(self.head_dim)) / (self.head_dim ** 0.5)
                    logits.append(score)

                weights = self.softmax(logits)
                head_output = []
                for j in range(self.head_dim):
                    head_output.append(sum(weights[t] * v_head[t][j] for t in range(len(v_head))))
                attended.extend(head_output)

            x = [
                out + res
                for out, res in zip(
                    self.linear(attended, self.state_dict["layer{0}.attn_wo".format(layer_idx)]),
                    residual,
                )
            ]

            residual = x
            x = self.rmsnorm(x)
            x = [item.relu() for item in self.linear(x, self.state_dict["layer{0}.mlp_fc1".format(layer_idx)])]
            x = [
                out + res
                for out, res in zip(
                    self.linear(x, self.state_dict["layer{0}.mlp_fc2".format(layer_idx)]),
                    residual,
                )
            ]

        return self.linear(x, self.state_dict["lm_head"])

    def train_step(self, seq, lr=0.01):
        if len(seq) < 2:
            return 0.0, {}

        keys = [[] for _ in range(self.n_layer)]
        values = [[] for _ in range(self.n_layer)]
        losses = []
        effective = [int(token) % self.vocab_size for token in seq[: self.block_size]]

        for pos in range(len(effective) - 1):
            token_id = effective[pos]
            target_id = effective[pos + 1]
            logits = self.forward(token_id, pos, keys, values)
            probs = self.softmax(logits)
            losses.append(-probs[target_id].log())

        loss = (1.0 / max(1, len(effective) - 1)) * sum(losses, Value(0.0))
        if math.isnan(loss.data) or math.isinf(loss.data):
            return 0.0, {"loss": 0.0, "grad_norm": 0.0, "max_bond": 0.0, "removed_neurons": 0}

        loss.backward()

        total_grad_norm_sq = 0.0
        max_bond = 0.0

        for param in self.params:
            param.grad = max(-1.0, min(1.0, param.grad))
            total_grad_norm_sq += param.grad * param.grad

            bond = self.oxytocin_bond(param.grad)
            self.update_slime_trace(param, bond)
            if bond > max_bond:
                max_bond = bond

            effective_lr = float(lr) * bond
            param.data -= effective_lr * param.grad
            param.grad = 0.0

        grad_norm = math.sqrt(total_grad_norm_sq)
        self.piston_push(grad_norm)
        self.loss_history.append(float(loss.data))

        removed = 0
        if len(self.loss_history) % 50 == 0:
            removed = self.structural_cleanup()

        metrics = {
            "loss": float(loss.data),
            "grad_norm": float(grad_norm),
            "max_bond": float(max_bond),
            "removed_neurons": int(removed),
        }
        return float(loss.data), metrics

    def train_on_sequences(self, sequences, steps=100, lr=0.01):
        if not sequences:
            return
        for _ in range(int(steps)):
            self.train_step(random.choice(sequences), lr=lr)

    def evaluate(self, sequences):
        if not sequences:
            return 0.0

        if isinstance(sequences[0], int):
            sequences = [sequences]

        losses = []
        for seq in sequences:
            if len(seq) < 2:
                continue

            keys = [[] for _ in range(self.n_layer)]
            values = [[] for _ in range(self.n_layer)]
            token_losses = []
            effective = [int(token) % self.vocab_size for token in seq[: self.block_size]]

            for pos in range(len(effective) - 1):
                token_id = effective[pos]
                target_id = effective[pos + 1]
                logits = self.forward(token_id, pos, keys, values)
                probs = self.softmax(logits)
                token_losses.append(-probs[target_id].log().data)

            if token_losses:
                losses.append(sum(token_losses) / len(token_losses))

        return float(sum(losses) / len(losses)) if losses else 0.0

    def generate(self, start_token, max_len=32, temperature=0.8):
        token = int(start_token) % self.vocab_size
        tokens = [token]
        keys = [[] for _ in range(self.n_layer)]
        values = [[] for _ in range(self.n_layer)]

        limit = max(1, min(int(max_len), self.block_size))
        for pos in range(limit - 1):
            logits = self.forward(tokens[-1], pos, keys, values)
            temp = max(float(temperature), 1e-3)
            scaled = [item.data / temp for item in logits]
            max_val = max(scaled)
            exps = [math.exp(max(-60.0, min(60.0, value - max_val))) for value in scaled]
            total = sum(exps)
            if total <= 0.0:
                total = 1e-12
            probs = [value / total for value in exps]
            next_token = int(np.random.choice(self.vocab_size, p=probs))
            tokens.append(next_token)

        return tokens

    def tokenize_text(self, text):
        return [self.char_to_id.get(ch, self.char_to_id["<UNK>"]) for ch in text]

    def detokenize_text(self, tokens):
        return "".join(self.id_to_char.get(int(token), "<UNK>") for token in tokens)

    def generate_text(self, prompt, max_len=50, temperature=0.8):
        prompt_tokens = self.tokenize_text(prompt) or [self.char_to_id["<BOS>"]]
        start = prompt_tokens[-1]
        generated = self.generate(start, max_len=max_len, temperature=temperature)
        return self.detokenize_text(prompt_tokens[:-1] + generated)

    # -----------------------------------------------------
    # metrics channel for NAS / beacon / eye
    # -----------------------------------------------------
    def quantize_metric(self, value, min_val, max_val, num_bins):
        if value < min_val:
            return 0
        if value > max_val:
            return num_bins - 1
        if max_val <= min_val:
            return 0
        return int((value - min_val) / (max_val - min_val) * (num_bins - 1))

    def metrics_to_tokens(self, metrics_list, ranges):
        tokens = []
        for metrics in metrics_list:
            for name, spec in ranges.items():
                if name not in metrics:
                    continue
                minv, maxv, bins = spec
                tokens.append(self.quantize_metric(float(metrics[name]), minv, maxv, bins))
        return tokens

    def train_on_metrics(self, metrics_seq, steps=100, lr=0.01):
        sequences = []
        stride = max(1, self.block_size // 2)

        for idx in range(0, max(0, len(metrics_seq) - self.block_size + 1), stride):
            sequences.append(metrics_seq[idx: idx + self.block_size])

        if sequences:
            self.train_on_sequences(sequences, steps=steps, lr=lr)

    # -----------------------------------------------------
    # weight io
    # -----------------------------------------------------
    def get_weights(self):
        return {
            name: [[param.data for param in row] for row in matrix]
            for name, matrix in self.state_dict.items()
        }

    def set_weights(self, weights):
        for name, matrix in weights.items():
            if name not in self.state_dict:
                continue

            for i, row in enumerate(matrix):
                if i >= len(self.state_dict[name]):
                    break

                for j, value in enumerate(row):
                    if j >= len(self.state_dict[name][i]):
                        break

                    self.state_dict[name][i][j].data = float(value)

    def save(self, path):
        payload = {
            "weights": self.get_weights(),
            "dna": self.dna,
            "slime_trace": dict((str(k), v) for k, v in self.slime_trace.items()),
            "meta": {
                "format": "microgpt_nas_pickle",
                "quant_mode": self.dna.get("quant_mode", "float"),
            },
        }
        _atomic_pickle_write(path, payload)

    def load(self, path):
        with open(path, "rb") as handle:
            payload = pickle.load(handle)

        if isinstance(payload, dict) and "weights" in payload:
            self.set_weights(payload["weights"])
            self.dna.update(payload.get("dna", {}))
        else:
            self.set_weights(payload)

        self._refresh_params(init_missing_trace=False)
        self.slime_trace = dict((id(p), 1.0) for p in self.params)

    # -----------------------------------------------------
    # quantization helpers
    # -----------------------------------------------------
    def _levels_for_bits(self, bits):
        bits = max(2, int(bits))
        return (2 ** (bits - 1)) - 1

    def _quantize_scalar(self, value, bits):
        levels = self._levels_for_bits(bits)
        clipped = max(-1.0, min(1.0, float(value)))
        q = int(round(clipped * levels))
        return q

    def _dequantize_scalar(self, qvalue, bits):
        levels = self._levels_for_bits(bits)
        return float(qvalue) / max(1, levels)

    def quantize_model(self, mode="slime_aware", int8_threshold=0.7, int4_threshold=0.3, inplace=False):
        mode = str(mode).strip().lower()
        exported = {}

        for name, matrix in self.state_dict.items():
            q_matrix = []
            for row in matrix:
                q_row = []
                for p in row:
                    value = p.data
                    bond = self.slime_trace.get(id(p), 1.0)

                    if mode == "int8":
                        qv = self._quantize_scalar(value, 8)
                        stored = qv
                        restored = self._dequantize_scalar(qv, 8)
                    elif mode == "int4":
                        qv = self._quantize_scalar(value, 4)
                        stored = qv
                        restored = self._dequantize_scalar(qv, 4)
                    else:
                        if bond >= int8_threshold:
                            stored = round(float(value), 4)
                            restored = float(stored)
                        elif bond >= int4_threshold:
                            qv = self._quantize_scalar(value, 8)
                            stored = {"q": qv, "bits": 8}
                            restored = self._dequantize_scalar(qv, 8)
                        else:
                            qv = self._quantize_scalar(value, 4)
                            stored = {"q": qv, "bits": 4}
                            restored = self._dequantize_scalar(qv, 4)

                    q_row.append(stored)

                    if inplace:
                        p.data = restored
                q_matrix.append(q_row)
            exported[name] = q_matrix

        if inplace:
            self.dna["quant_mode"] = mode

        self.quant_history.append({
            "mode": mode,
            "changed_params": len(self.params),
        })

        return exported

    def export_quantized_state(self, path=None, mode=None):
        if mode is None:
            mode = DEFAULT_IMPORT_QUANT_MODE

        runtime_model_config = {
            "vocab_size": self.vocab_size,
            "n_layer": self.n_layer,
            "n_embd": self.n_embd,
            "block_size": self.block_size,
            "n_head": self.n_head,
        }
        import_diag = _dict_or_empty(getattr(self, "last_import_diagnostics", {}))
        payload_meta = {
            "source": str(import_diag.get("source") or "nas_microgpt"),
        }
        for key in ("device_id", "cycle", "best_val", "timestamp", "payload_branch", "transport", "source_path"):
            value = import_diag.get(key)
            if value not in (None, ""):
                payload_meta[key] = value
        if import_diag.get("incoming_model_config"):
            payload_meta["incoming_model_config"] = _dict_or_empty(import_diag.get("incoming_model_config"))
        if import_diag.get("model_config_mismatch"):
            payload_meta["model_config_mismatch"] = _dict_or_empty(import_diag.get("model_config_mismatch"))
        if import_diag.get("loaded_keys"):
            payload_meta["loaded_keys"] = list(import_diag.get("loaded_keys") or [])
        if import_diag.get("skipped_keys"):
            payload_meta["skipped_keys"] = list(import_diag.get("skipped_keys") or [])
        if import_diag.get("unknown_weight_keys"):
            payload_meta["unknown_weight_keys"] = list(import_diag.get("unknown_weight_keys") or [])
        if import_diag.get("transfer_manifest"):
            payload_meta["transfer_manifest"] = _dict_or_empty(import_diag.get("transfer_manifest"))
        if import_diag.get("partial_load_ratio") is not None:
            payload_meta["partial_load_ratio"] = float(import_diag.get("partial_load_ratio"))

        payload = {
            "format": "janus_quantized_weights_v1",
            "quant_mode": str(mode).strip().lower(),
            "weights": self.quantize_model(mode=mode, inplace=False),
            "dna": dict(self.dna),
            "model_config": runtime_model_config,
            "meta": payload_meta,
        }

        target_path = path or ACTIVE_QUANTIZED_JSON
        _atomic_json_write(target_path, payload)

        try:
            active_meta = {
                "quant_mode": payload["quant_mode"],
                "source": payload_meta.get("source", "nas_microgpt"),
                "n_layer": self.n_layer,
                "n_embd": self.n_embd,
                "n_head": self.n_head,
                "block_size": self.block_size,
                "vocab_size": self.vocab_size,
                "runtime_model_config": runtime_model_config,
            }
            for key in ("device_id", "cycle", "best_val", "timestamp", "payload_branch", "transport", "source_path"):
                value = payload_meta.get(key)
                if value not in (None, ""):
                    active_meta[key] = value
            if payload_meta.get("incoming_model_config"):
                active_meta["incoming_model_config"] = _dict_or_empty(payload_meta.get("incoming_model_config"))
            if payload_meta.get("model_config_mismatch"):
                active_meta["model_config_mismatch"] = _dict_or_empty(payload_meta.get("model_config_mismatch"))
            if payload_meta.get("loaded_keys"):
                active_meta["loaded_keys"] = list(payload_meta.get("loaded_keys") or [])
            if payload_meta.get("skipped_keys"):
                active_meta["skipped_keys"] = list(payload_meta.get("skipped_keys") or [])
            if payload_meta.get("unknown_weight_keys"):
                active_meta["unknown_weight_keys"] = list(payload_meta.get("unknown_weight_keys") or [])
            if payload_meta.get("transfer_manifest"):
                active_meta["transfer_manifest"] = _dict_or_empty(payload_meta.get("transfer_manifest"))
            if payload_meta.get("partial_load_ratio") is not None:
                active_meta["partial_load_ratio"] = float(payload_meta.get("partial_load_ratio"))
            _atomic_json_write(
                ACTIVE_MODEL_META_JSON,
                active_meta,
            )
        except Exception:
            pass

        return payload

    def apply_quantized_state(self, payload_or_path):
        if isinstance(payload_or_path, str):
            with open(payload_or_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        else:
            payload = payload_or_path

        weights = payload.get("weights", {})
        quant_mode = payload.get("quant_mode", "float")
        meta = _dict_or_empty(payload.get("meta"))
        incoming_model_config = _dict_or_empty(payload.get("model_config"))
        runtime_model_config = {
            "vocab_size": self.vocab_size,
            "n_layer": self.n_layer,
            "n_embd": self.n_embd,
            "block_size": self.block_size,
            "n_head": self.n_head,
        }
        model_config_mismatch = _build_model_config_mismatch(incoming_model_config, runtime_model_config)

        normalized_weights = {}
        normalized_sources = {}
        alias_hits = {}
        alias_duplicates = []
        unknown_weight_keys = []

        for raw_name, matrix in (weights.items() if isinstance(weights, dict) else []):
            normalized_name = _normalize_import_weight_name(raw_name)
            if normalized_name not in self.state_dict:
                unknown_weight_keys.append(str(raw_name))
                continue

            previous_name = normalized_sources.get(normalized_name)
            if previous_name is None:
                normalized_weights[normalized_name] = matrix
                normalized_sources[normalized_name] = str(raw_name)
                if normalized_name != raw_name:
                    alias_hits[str(raw_name)] = normalized_name
                continue

            previous_is_alias = str(previous_name) != normalized_name
            current_is_native = str(raw_name) == normalized_name
            if current_is_native and previous_is_alias:
                normalized_weights[normalized_name] = matrix
                normalized_sources[normalized_name] = str(raw_name)
                alias_duplicates.append(str(previous_name))
            else:
                alias_duplicates.append(str(raw_name))
            if normalized_name != raw_name:
                alias_hits[str(raw_name)] = normalized_name

        loaded_keys = []
        for name, matrix in normalized_weights.items():
            if name not in self.state_dict or not isinstance(matrix, list):
                continue

            for i, row in enumerate(matrix):
                if i >= len(self.state_dict[name]):
                    break

                for j, value in enumerate(row):
                    if j >= len(self.state_dict[name][i]):
                        break

                    restored = None

                    if isinstance(value, dict):
                        qv = value.get("q", 0)
                        bits = int(value.get("bits", 8))
                        restored = self._dequantize_scalar(qv, bits)
                    elif quant_mode == "int8":
                        restored = self._dequantize_scalar(value, 8)
                    elif quant_mode == "int4":
                        restored = self._dequantize_scalar(value, 4)
                    else:
                        restored = float(value)

                    self.state_dict[name][i][j].data = float(restored)
            loaded_keys.append(name)

        self.dna["quant_mode"] = quant_mode
        self._refresh_params(init_missing_trace=False)
        self.slime_trace = dict((id(p), 1.0) for p in self.params)

        skipped_keys = [name for name in self.state_dict.keys() if name not in loaded_keys]
        transfer_manifest = _dict_or_empty(meta.get("transfer_manifest"))
        if alias_hits or alias_duplicates:
            transfer_manifest = dict(transfer_manifest)
            if alias_hits:
                transfer_manifest["microgpt_alias_hits"] = dict(alias_hits)
            if alias_duplicates:
                transfer_manifest["microgpt_alias_duplicates"] = list(alias_duplicates)
        partial_load_ratio = float(len(loaded_keys)) / float(max(1, len(self.state_dict)))
        self.last_import_diagnostics = {
            "source": str(meta.get("source") or "pc_or_external"),
            "device_id": meta.get("device_id"),
            "cycle": meta.get("cycle"),
            "best_val": meta.get("best_val"),
            "timestamp": meta.get("timestamp"),
            "payload_branch": str(payload.get("payload_branch") or meta.get("payload_branch") or ""),
            "transport": str(payload.get("transport") or meta.get("transport") or ""),
            "source_path": str(meta.get("source_path") or ""),
            "incoming_model_config": incoming_model_config,
            "runtime_model_config": runtime_model_config,
            "model_config_mismatch": model_config_mismatch,
            "loaded_keys": list(loaded_keys),
            "skipped_keys": list(skipped_keys),
            "unknown_weight_keys": list(unknown_weight_keys),
            "partial_load_ratio": partial_load_ratio,
            "transfer_manifest": transfer_manifest,
        }

        try:
            _atomic_json_write(
                ACTIVE_MODEL_META_JSON,
                {
                    "quant_mode": quant_mode,
                    "source": self.last_import_diagnostics.get("source", "pc_or_external"),
                    "device_id": self.last_import_diagnostics.get("device_id"),
                    "cycle": self.last_import_diagnostics.get("cycle"),
                    "best_val": self.last_import_diagnostics.get("best_val"),
                    "timestamp": self.last_import_diagnostics.get("timestamp"),
                    "payload_branch": self.last_import_diagnostics.get("payload_branch"),
                    "transport": self.last_import_diagnostics.get("transport"),
                    "source_path": self.last_import_diagnostics.get("source_path"),
                    "n_layer": self.n_layer,
                    "n_embd": self.n_embd,
                    "n_head": self.n_head,
                    "block_size": self.block_size,
                    "vocab_size": self.vocab_size,
                    "runtime_model_config": runtime_model_config,
                    "incoming_model_config": incoming_model_config,
                    "model_config_mismatch": model_config_mismatch,
                    "loaded_keys": list(loaded_keys),
                    "skipped_keys": list(skipped_keys),
                    "unknown_weight_keys": list(unknown_weight_keys),
                    "partial_load_ratio": partial_load_ratio,
                    "transfer_manifest": transfer_manifest,
                },
            )
        except Exception:
            pass

        return True

    def estimate_memory_bytes(self, assume_float_bytes=8):
        param_count = len(self.params)
        float_bytes = int(param_count * int(assume_float_bytes))
        int8_bytes = int(param_count)
        int4_bytes = int(max(1, param_count // 2))

        mixed_bytes = 0.0
        for p in self.params:
            bond = self.slime_trace.get(id(p), 1.0)
            if bond >= 0.7:
                mixed_bytes += 2.0
            elif bond >= 0.3:
                mixed_bytes += 1.0
            else:
                mixed_bytes += 0.5

        return {
            "params": int(param_count),
            "float_bytes": int(float_bytes),
            "int8_bytes": int(int8_bytes),
            "int4_bytes": int(int4_bytes),
            "slime_mixed_bytes": int(mixed_bytes),
        }
