# -*- coding: utf-8 -*-
"""
[ПРОЕКТ ЯНУС: QUANTUM CORE v1.0 - THREADED SINGULARITY]
Роль: Изолированная математическая библиотека.
Суть: Выполняет тяжелые тензорные вычисления (MicroGPT) в пуле потоков 
внутри процесса blood_core.py.
"""

import os
import math
import random
import json
import logging
import pickle
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("JANUS.QUANTUM")
_OLLAMA_BACKOFF_STATE = {
    "until": 0.0,
    "last_error": "",
    "last_log_ts": 0.0,
}

# --- ФУНДАМЕНТ НАСКАЛЬНОГО ЯЗЫКА ---
SEMANTIC_DICT = {
    "analyze": "\U0001F50D",   # Лупа
    "protect": "\U0001F6E1",   # Щит
    "evolve": "\U0001F9EC",    # ДНК
    "danger": "\u26A0\uFE0F",  # Внимание
    "system": "\U0001F916",    # Робот
    "memory": "\U0001F4BE",    # Дискета
    "idea": "\U0001F4A1",      # Идея
    "connect": "\U0001F517",   # Звено
    "delete": "\u274C",        # Крест
    "approve": "\u2705"        # Галочка
}
REVERSE_DICT = {v: k for k, v in SEMANTIC_DICT.items()}
VOCAB = list(SEMANTIC_DICT.values())

# ==============================================================================
# 1. PURE PYTHON AUTOGRAD & MICRO-GPT (Тяжелая математика)
# ==============================================================================
class Value:
    __slots__ = ('data', 'grad', '_children', '_local_grads')
    def __init__(self, data, children=(), local_grads=()):
        self.data = data
        self.grad = 0
        self._children = children
        self._local_grads = local_grads

    def __add__(self, other):
        other = other if isinstance(other, Value) else Value(other)
        return Value(self.data + other.data, (self, other), (1, 1))

    def __mul__(self, other):
        other = other if isinstance(other, Value) else Value(other)
        return Value(self.data * other.data, (self, other), (other.data, self.data))

    def __pow__(self, other):
        return Value(self.data**other, (self,), (other * self.data**(other-1),))

    def log(self):
        val = self.data if self.data > 1e-15 else 1e-15
        return Value(math.log(val), (self,), (1/val,))

    def exp(self):
        return Value(math.exp(self.data), (self,), (math.exp(self.data),))

    def relu(self):
        return Value(max(0, self.data), (self,), (float(self.data > 0),))

    def __neg__(self): return self * -1
    def __radd__(self, other): return self + other
    def __sub__(self, other): return self + (-other)
    def __rsub__(self, other): return other + (-self)
    def __rmul__(self, other): return self * other
    def __truediv__(self, other): return self * other**-1

    def backward(self):
        topo = []
        visited = set()
        def build_topo(v):
            if v not in visited:
                visited.add(v)
                for child in v._children:
                    build_topo(child)
                topo.append(v)
        build_topo(self)
        self.grad = 1
        for v in reversed(topo):
            for child, local_grad in zip(v._children, v._local_grads):
                child.grad += local_grad * v.grad

class MicroGPT:
    def __init__(self, vocab_size, n_layer=1, n_embd=16, block_size=16, n_head=4):
        self.vocab_size = max(vocab_size, 2)
        self.n_layer = n_layer
        self.n_embd = n_embd
        self.block_size = block_size
        self.n_head = n_head
        self.head_dim = n_embd // n_head

        matrix = lambda nout, nin, std=0.08: [[Value(random.gauss(0, std)) for _ in range(nin)] for _ in range(nout)]
        self.state_dict = {
            'wte': matrix(self.vocab_size, n_embd),
            'wpe': matrix(block_size, n_embd),
            'lm_head': matrix(self.vocab_size, n_embd)
        }
        for i in range(n_layer):
            self.state_dict[f'layer{i}.attn_wq'] = matrix(n_embd, n_embd)
            self.state_dict[f'layer{i}.attn_wk'] = matrix(n_embd, n_embd)
            self.state_dict[f'layer{i}.attn_wv'] = matrix(n_embd, n_embd)
            self.state_dict[f'layer{i}.attn_wo'] = matrix(n_embd, n_embd)
            self.state_dict[f'layer{i}.mlp_fc1'] = matrix(4 * n_embd, n_embd)
            self.state_dict[f'layer{i}.mlp_fc2'] = matrix(n_embd, 4 * n_embd)

        self.params = [p for mat in self.state_dict.values() for row in mat for p in row]

    def linear(self, x, w):
        return [sum(wi * xi for wi, xi in zip(wo, x)) for wo in w]

    def softmax(self, logits):
        max_val = max(val.data if isinstance(val, Value) else val for val in logits)
        exps = [(val - max_val).exp() if isinstance(val, Value) else math.exp(val - max_val) for val in logits]
        total = sum(e.data if isinstance(e, Value) else e for e in exps)
        return [e / total for e in exps]

    def rmsnorm(self, x):
        ms = sum(xi.data * xi.data if isinstance(xi, Value) else xi * xi for xi in x) / len(x)
        return [xi * ((ms + 1e-5) ** -0.5) for xi in x]

    def forward(self, token_id, pos_id, keys, values):
        x = self.rmsnorm([t + p for t, p in zip(self.state_dict['wte'][token_id], self.state_dict['wpe'][pos_id])])
        for li in range(self.n_layer):
            x_residual = x
            x = self.rmsnorm(x)
            q = self.linear(x, self.state_dict[f'layer{li}.attn_wq'])
            k = self.linear(x, self.state_dict[f'layer{li}.attn_wk'])
            v = self.linear(x, self.state_dict[f'layer{li}.attn_wv'])
            keys[li].append(k)
            values[li].append(v)

            x_attn = []
            for h in range(self.n_head):
                hs = h * self.head_dim
                q_h = q[hs:hs+self.head_dim]
                k_h = [ki[hs:hs+self.head_dim] for ki in keys[li]]
                v_h = [vi[hs:hs+self.head_dim] for vi in values[li]]

                attn_logits = [sum(q_h[j] * k_h[t][j] for j in range(self.head_dim)) / (self.head_dim**0.5) for t in range(len(k_h))]
                attn_weights = self.softmax(attn_logits)
                x_attn.extend([sum(attn_weights[t] * v_h[t][j] for t in range(len(v_h))) for j in range(self.head_dim)])

            x = [a + b for a, b in zip(self.linear(x_attn, self.state_dict[f'layer{li}.attn_wo']), x_residual)]
            x_residual = x
            x = self.rmsnorm(x)
            x = [xi.relu() for xi in self.linear(x, self.state_dict[f'layer{li}.mlp_fc1'])]
            x = [a + b for a, b in zip(self.linear(x, self.state_dict[f'layer{li}.mlp_fc2']), x_residual)]

        return self.linear(x, self.state_dict['lm_head'])

# ==============================================================================
# 2. QUANTUM ENGINE (Обертка для работы из blood_core)
# ==============================================================================
class QuantumEngine:
    def __init__(self, model_path="quantum_weights.pkl"):
        self.model_path = model_path
        self.vocab = VOCAB
        self.vocab_size = len(self.vocab)
        self.model = MicroGPT(vocab_size=self.vocab_size, n_layer=1, n_embd=16, block_size=16, n_head=2)
        
        # Вот эта строка создает "теневой поток" внутри процесса blood_core:
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="QuantumMath")
        
        self._load_weights()

    def _load_weights(self):
        try:
            if os.path.exists(self.model_path):
                with open(self.model_path, 'rb') as f:
                    state_dict = pickle.load(f)
                self.model.state_dict = state_dict
                logger.info("\U0001F9E0 QUANTUM: Веса Сингулярности успешно загружены.")
        except Exception as e:
            logger.error(f"\u274C QUANTUM: Ошибка загрузки весов: {e}")

    def _save_weights(self):
        try:
            with open(self.model_path, 'wb') as f:
                pickle.dump(self.model.state_dict, f)
        except Exception as e:
            logger.error(f"\u274C QUANTUM: Ошибка сохранения: {e}")

    def _sync_train(self, docs, steps, learning_rate=0.01):
        if not docs: return 0.0
        for step in range(steps):
            doc = random.choice(docs)
            ids = [self.vocab.index(char) for char in doc if char in self.vocab]
            if len(ids) < 2: continue

            n = min(self.model.block_size, len(ids) - 1)
            keys = [[] for _ in range(self.model.n_layer)]
            values = [[] for _ in range(self.model.n_layer)]
            losses = []

            for pos in range(n):
                token_id = ids[pos]
                target_id = ids[pos + 1]
                logits = self.model.forward(token_id, pos, keys, values)
                probs = self.model.softmax(logits)
                loss_t = -probs[target_id].log()
                losses.append(loss_t)

            if not losses: continue

            loss = (1.0 / n) * sum(losses, Value(0.0))
            if math.isnan(loss.data): continue

            loss.backward()

            for p in self.model.params:
                if p.grad is not None:
                    p.grad = max(-1.0, min(1.0, p.grad))
                    p.data -= learning_rate * p.grad
                    p.grad = 0

        self._save_weights()
        return float(loss.data) if 'loss' in locals() else 0.0

    def _sync_hallucinate(self, entropy=0.5, max_len=11):
        keys = [[] for _ in range(self.model.n_layer)]
        values = [[] for _ in range(self.model.n_layer)]
        start_id = random.randint(0, self.vocab_size - 1)
        sample_ids = [start_id]

        for pos in range(1, max_len):
            logits = self.model.forward(sample_ids[-1], pos % self.model.block_size, keys, values)
            temp = max(0.1, (entropy / 100.0) * 2.0)
            raw_logits = [l.data / temp for l in logits]
            max_val = max(raw_logits)
            exps = [math.exp(v - max_val) for v in raw_logits]
            probs = [e / sum(exps) for e in exps]
            
            next_id = random.choices(range(self.vocab_size), weights=probs)[0]
            sample_ids.append(next_id)

        quanta = [self.vocab[i] for i in sample_ids]
        semantics = [REVERSE_DICT.get(q, "unknown") for q in quanta]

        result = {
            "cipher": "".join(quanta),
            "semantics": semantics,
            "entropy_state": entropy
        }
        return json.dumps(result, ensure_ascii=False)

    async def train_async(self, docs, steps=10):
        loop = asyncio.get_running_loop()
        try:
            loss = await loop.run_in_executor(self.executor, self._sync_train, docs, steps)
            if loss > 0:
                logger.info(f"\u2728 QUANTUM: Цикл медитации завершен. Loss: {loss:.4f}")
        except Exception as e:
            logger.error(f"\u274C QUANTUM TRAIN FAIL: {e}")

    async def hallucinate_json(self, entropy=50):
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(self.executor, self._sync_hallucinate, entropy, 6)
        except Exception as e:
            logger.error(f"\u274C QUANTUM HALLUCINATE FAIL: {e}")
            return json.dumps({"cipher": "\u274C", "semantics": ["error"]})

# Глобальный экземпляр для импорта в blood_core
class LocalModelEngine:
    """
    Backward-compatible local model facade expected by services/ai_engine.py.
    It reuses the shared QuantumEngine and converts its symbolic output into
    a plain text answer.
    """
    def __init__(self, model_type="microgpt", model_path=None, config=None):
        self.model_type = model_type
        self.model_path = model_path or "quantum_weights.pkl"
        self.config = config or {}
        self.ollama_url = os.getenv("JANUS_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
        self.ollama_model = os.getenv("JANUS_OLLAMA_MODEL", "qwen2.5:0.5b").strip()
        self.ollama_fallback_model = os.getenv("JANUS_OLLAMA_FALLBACK_MODEL", "").strip()
        self.agent_bridge_url = os.getenv("JANUS_AGENT_BRIDGE_URL", "http://127.0.0.1:18091").rstrip("/")
        try:
            self.ollama_timeout = float(os.getenv("JANUS_OLLAMA_TIMEOUT", "18"))
        except Exception:
            self.ollama_timeout = 18.0
        try:
            self.agent_timeout = float(os.getenv("JANUS_AGENT_TIMEOUT", "18"))
        except Exception:
            self.agent_timeout = 18.0

    async def _list_ollama_models(self):
        timeout = aiohttp.ClientTimeout(total=self.ollama_timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get("{0}/api/tags".format(self.ollama_url)) as resp:
                if resp.status != 200:
                    raise RuntimeError("ollama tags status={0}".format(resp.status))
                payload = await resp.json()
        names = []
        for item in payload.get("models", []):
            name = item.get("name")
            if name:
                names.append(name)
        return names

    async def _resolve_ollama_model(self):
        models = await self._list_ollama_models()
        if not models:
            raise RuntimeError("ollama has no installed models")
        preferred = [self.ollama_model, self.ollama_fallback_model, "qwen2.5:0.5b", "phi3:mini", "llama3.2:1b"]
        for candidate in preferred:
            if candidate and candidate in models:
                return candidate
        return models[0]

    async def _generate_via_ollama(self, prompt, max_tokens=100, temperature=0.7):
        model_name = await self._resolve_ollama_model()
        payload = {
            "model": model_name,
            "prompt": str(prompt),
            "stream": False,
            "options": {
                "temperature": float(max(0.05, min(2.0, temperature))),
                "num_predict": int(max(32, min(512, max_tokens))),
            },
        }
        timeout = aiohttp.ClientTimeout(total=max(self.ollama_timeout, 8))
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post("{0}/api/generate".format(self.ollama_url), json=payload) as resp:
                text = await resp.text()
                if resp.status != 200:
                    raise RuntimeError("ollama generate status={0} body={1}".format(resp.status, text[:240]))
                try:
                    data = json.loads(text)
                except Exception as e:
                    raise RuntimeError("ollama invalid json: {0} :: {1}".format(e, text[:240]))
        answer = (data.get("response") or "").strip()
        if not answer:
            raise RuntimeError("ollama empty response")
        return answer

    async def _generate_via_agent_bridge(self, prompt, max_tokens=100, temperature=0.7):
        payload = {
            "query": str(prompt),
            "source": "titan_fallback",
            "state": "calm",
            "max_tokens": int(max(32, min(512, max_tokens))),
            "temperature": float(max(0.05, min(2.0, temperature))),
        }
        timeout = aiohttp.ClientTimeout(total=max(self.agent_timeout, 8))
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post("{0}/api/agent/think".format(self.agent_bridge_url), json=payload) as resp:
                text = await resp.text()
                if resp.status != 200:
                    raise RuntimeError("agent bridge status={0} body={1}".format(resp.status, text[:240]))
                try:
                    data = json.loads(text)
                except Exception as e:
                    raise RuntimeError("agent bridge invalid json: {0} :: {1}".format(e, text[:240]))

        answer = (data.get("reply") or data.get("summary") or "").strip()
        if not answer:
            raise RuntimeError("agent bridge empty response")
        return answer

    async def generate(self, prompt, max_tokens=100, temperature=0.7):
        now = asyncio.get_running_loop().time()
        if _OLLAMA_BACKOFF_STATE["until"] > now:
            try:
                answer = await self._generate_via_agent_bridge(prompt, max_tokens=max_tokens, temperature=temperature)
                logger.info("AGENT FALLBACK OK")
                return answer
            except Exception as bridge_error:
                logger.warning("AGENT FALLBACK FAIL: %s", bridge_error)
        try:
            return await self._generate_via_ollama(prompt, max_tokens=max_tokens, temperature=temperature)
        except Exception as e:
            error_text = str(e).strip() or e.__class__.__name__
            lowered = error_text.lower()
            if any(token in lowered for token in ("11434", "connect", "connection refused", "timeout")):
                _OLLAMA_BACKOFF_STATE["until"] = now + 30.0
                _OLLAMA_BACKOFF_STATE["last_error"] = error_text
                if now - _OLLAMA_BACKOFF_STATE["last_log_ts"] >= 30.0:
                    logger.warning("OLLAMA OFFLINE BACKOFF: %s", error_text)
                    _OLLAMA_BACKOFF_STATE["last_log_ts"] = now
                try:
                    answer = await self._generate_via_agent_bridge(prompt, max_tokens=max_tokens, temperature=temperature)
                    logger.info("AGENT FALLBACK OK")
                    return answer
                except Exception as bridge_error:
                    logger.warning("AGENT FALLBACK FAIL: %s", bridge_error)
            else:
                try:
                    answer = await self._generate_via_agent_bridge(prompt, max_tokens=max_tokens, temperature=temperature)
                    logger.info("AGENT FALLBACK OK")
                    return answer
                except Exception as bridge_error:
                    logger.warning("AGENT FALLBACK FAIL: %s", bridge_error)
                logger.warning("OLLAMA GENERATE FAIL: %s", error_text)
            entropy = int(max(1, min(100, temperature * 100)))
            raw = await quantum_engine.hallucinate_json(entropy=entropy)
            prompt_preview = str(prompt).strip().splitlines()[-1][:120] if str(prompt).strip() else "JANUS"
            try:
                payload = json.loads(raw)
            except Exception:
                return raw

            semantics = [item for item in payload.get("semantics", []) if item and item != "unknown"]
            cipher = payload.get("cipher", "")

            if semantics:
                return f"{prompt_preview} :: {' '.join(semantics[: min(8, max_tokens)])}".strip()
            if cipher:
                return f"{prompt_preview} :: {cipher}".strip()
            return prompt_preview

class SemanticQuantum:
    """
    Backward-compatible adapter expected by blood_core.py.
    """
    def __init__(self, engine):
        self.engine = engine

    async def run_physarum_search(self, steps=3000):
        docs = []
        if getattr(self.engine, "memory", None) and hasattr(self.engine.memory, "fetch_structured_memories"):
            try:
                docs = await self.engine.memory.fetch_structured_memories(limit=min(500, max(24, steps // 12)))
            except TypeError:
                docs = await self.engine.memory.fetch_structured_memories()
            except Exception as e:
                logger.error(f"\u274C SEMANTIC QUANTUM FETCH FAIL: {e}")
                docs = []

        docs = [doc for doc in docs if isinstance(doc, str) and doc.strip()]
        if docs:
            train_steps = max(6, min(96, steps // 80))
            await quantum_engine.train_async(docs, steps=train_steps)
        return {"docs": len(docs), "steps": steps}

    async def generate_thought(self, temperature=0.7):
        entropy = int(max(1, min(100, temperature * 100)))
        raw = await quantum_engine.hallucinate_json(entropy=entropy)
        try:
            payload = json.loads(raw)
        except Exception:
            return raw

        semantics = [item for item in payload.get("semantics", []) if item and item != "unknown"]
        cipher = payload.get("cipher", "")
        if semantics:
            return " ".join(semantics[:8])
        return cipher or "signal"

quantum_engine = QuantumEngine()
