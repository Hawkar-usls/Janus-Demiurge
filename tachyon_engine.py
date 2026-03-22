#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TACHYON ENGINE — модуль предсказания.
v3.2 — добавлен evaluate_actions для поддержки выбора действий агента.
"""

import numpy as np
import logging
import copy
import random
from sklearn.neural_network import MLPRegressor
from sklearn.multioutput import MultiOutputRegressor
import joblib
import os
from config import RAW_LOGS_DIR
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger("JANUS.TACHYON")

CONFIG = {
    'model_dir': RAW_LOGS_DIR,
    'outcome_model': 'tachyon_outcome_model.pkl',
    'symbiosis_model': 'tachyon_symbiosis_model.pkl',
    'mlp_hidden_layers': (64, 32),
    'symbiosis_hidden_layers': (32, 16),
    'max_dataset_size': 2000,
    'symbiosis_dataset_size': 2000,
    'min_samples_for_train': 50,
    'symbiosis_retrain_freq': 20,
    'default_batch_factor_gaming': 0.15,
    'default_parallel_factor_gaming': 0.05,
    'default_pause_factor_gaming': 5.0,
    'default_batch_factor': 1.0,
    'default_parallel_factor': 1.0,
    'default_pause_factor': 1.0,
    'batch_factor_clip': (0.05, 1.5),
    'parallel_factor_clip': (0.01, 1.5),
    'pause_factor_clip': (0.5, 10.0)
}


class TachyonEngine:
    """Классический MLP-предсказатель (совместимость с ядром)."""

    def __init__(self, model_path: Optional[str] = None):
        self.dataset = []
        self.trained = False
        self.model = None
        self.model_path = model_path or os.path.join(CONFIG['model_dir'], CONFIG['outcome_model'])
        self.load_model()

        self.trained_score = False
        self.trained_mi = False
        self.anti_trained = False

        self.symbiosis_dataset = []
        self.symbiosis_model = None
        self.symbiosis_model_path = os.path.join(CONFIG['model_dir'], CONFIG['symbiosis_model'])
        self._load_symbiosis_model()

    def encode_config(self, config: Dict[str, Any], step_time: Optional[float] = None) -> np.ndarray:
        base = [
            config.get("lr", 0.001),
            config.get("gain", 1.0),
            config.get("temperature", 1.0),
            config.get("n_embd", 256) / 768.0,
            config.get("n_head", 8) / 16.0,
            config.get("n_layer", 6) / 12.0
        ]
        if step_time is not None:
            base.append(step_time / 100.0)
        return np.array(base, dtype=float)

    def encode_features(self, features: Dict[str, Any]) -> np.ndarray:
        vec = [
            features.get('importance', 0.5),
            features.get('prompt_len', 50) / 100.0,
            features.get('steps', 50) / 100.0,
            features.get('seed_mod', 0) / 1000.0,
            features.get('cpu', 0) / 100.0,
            features.get('ram', 0) / 100.0,
            features.get('gpu', 0) / 100.0,
        ]
        event_type = features.get('event_type', 'unknown')
        event_map = {'RECORD':0, 'EXTINCTION':1, 'NEW_SPECIES':2, 'RAID':3,
                     'INSTITUTION_FOUNDED':4, 'WORMHOLE':5, 'DEFAULT':6}
        idx = event_map.get(event_type, 6)
        one_hot = [0]*7
        one_hot[idx] = 1
        vec.extend(one_hot)
        style = features.get('style', '')
        style_map = {'default':0, 'epic':1, 'dark':2, 'cosmic':3, 'battle':4}
        style_idx = style_map.get(style, 0)
        vec.append(style_idx / 5.0)
        return np.array(vec, dtype=float)

    def add_sample(self, *args, **kwargs) -> None:
        if len(args) == 2 and isinstance(args[0], dict) and isinstance(args[1], dict):
            features, outcome = args
            x = self.encode_features(features)
            y = np.array([
                outcome.get('quality', 0.0),
                outcome.get('time', 0.0) / 10.0,
                outcome.get('size', 0.0) / 1000.0,
                outcome.get('score', 0.0)
            ])
            self.dataset.append((x, y))
        elif len(args) == 4:
            config, score, mi, step_time = args
            x = self.encode_config(config, step_time)
            y = np.array([score, 0.0, 0.0, score])
            self.dataset.append((x, y))
        else:
            raise TypeError("add_sample() принимает либо 2, либо 4 аргумента")

        if len(self.dataset) > CONFIG['max_dataset_size']:
            self.dataset = self.dataset[-CONFIG['max_dataset_size']:]

    def train(self) -> bool:
        if len(self.dataset) < CONFIG['min_samples_for_train']:
            return False
        X = np.array([item[0] for item in self.dataset])
        Y = np.array([item[1] for item in self.dataset])
        try:
            base_model = MLPRegressor(
                hidden_layer_sizes=CONFIG['mlp_hidden_layers'],
                activation='relu',
                solver='adam',
                max_iter=500,
                random_state=42,
                early_stopping=True,
                validation_fraction=0.1
            )
            self.model = MultiOutputRegressor(base_model, n_jobs=1)
            self.model.fit(X, Y)
            self.trained = True
            logger.info(f"🔮 Tachyon обучен на {len(self.dataset)} примерах")
            joblib.dump(self.model, self.model_path)
            return True
        except Exception as e:
            logger.error(f"Ошибка обучения Tachyon: {e}", exc_info=True)
            return False

    def predict_outcome(self, features: Dict[str, Any]) -> Optional[Dict[str, float]]:
        if not self.trained or self.model is None:
            return None
        x = self.encode_features(features).reshape(1, -1)
        try:
            y_pred = self.model.predict(x)[0]
            return {
                'quality': float(y_pred[0]),
                'time': float(y_pred[1]) * 10.0,
                'size': float(y_pred[2]) * 1000.0,
                'score': float(y_pred[3])
            }
        except Exception as e:
            logger.error(f"Ошибка предсказания: {e}")
            return None

    def predict_world(self, world) -> Dict[str, Any]:
        future = {
            "population": len(world.population) + random.randint(-2, 2),
            "conflict": getattr(world, 'global_conflict', 0) + random.uniform(-0.1, 0.1),
            "economy": getattr(world, 'economy', None) and world.economy.get_stability() if hasattr(world.economy, 'get_stability') else 0.5,
            "meaning": getattr(world, 'meaning', None) and world.meaning.current_goal or "unknown"
        }
        return future

    def learn(self, features: Dict[str, Any], outcome: Dict[str, Any], weight: float = 1.0) -> None:
        self.add_sample(features, outcome)
        if len(self.dataset) % 50 == 0 and len(self.dataset) >= CONFIG['min_samples_for_train']:
            self.train()

    def load_model(self) -> None:
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                self.trained = True
                logger.info("🔮 Tachyon модель загружена")
            except Exception as e:
                logger.warning(f"Не удалось загрузить модель: {e}")

    def propose_future(self, memory, samples: int = 20, step_time: Optional[float] = None, use_mi: bool = False) -> Optional[Dict]:
        if not hasattr(memory, 'propose'):
            return None
        for _ in range(samples):
            result = memory.propose()
            if result:
                config, mutated, miracle = result
                if config:
                    return config
        return None

    def evaluate_actions(self, state: Any, actions: List[str]) -> Dict[str, float]:
        """
        Оценивает каждое действие, предсказывая его результат.
        state — состояние (JanusRPGState), actions — список строк.
        Возвращает словарь {action: score}.
        """
        if not self.trained:
            return {a: random.uniform(0,1) for a in actions}
        scores = {}
        for action in actions:
            features = {
                'event_type': action,  # упрощённо
                'importance': 1.0,
                'prompt_len': len(action),
                'steps': 50,
                'seed_mod': hash(state) % 1000,
                'cpu': 0,
                'ram': 0,
                'gpu': 0,
                'style': 'default'
            }
            pred = self.predict_outcome(features)
            if pred:
                scores[action] = pred.get('score', 0.5)
            else:
                scores[action] = 0.5
        return scores

    # --- Методы для симбиоза (оставлены) ---
    def _load_symbiosis_model(self): ...
    def _encode_symbiosis_features(self, features): ...
    def suggest_symbiosis(self, features): ...
    def report_symbiosis_outcome(self, features, params, had_fps_drop): ...
    def _train_symbiosis_model(self): ...

    def train_score(self): pass
    def train_mi(self): pass
    def train_anti(self): pass


class TachyonRollout:
    """Multi-step предсказатель для RL."""

    def __init__(self, env, depth: int = 3, simulations: int = 5):
        self.env = env
        self.depth = max(1, depth)
        self.simulations = max(1, simulations)

    def evaluate_actions(self, state: Any, actions: List[str]) -> Dict[str, float]:
        scores = {}
        for action in actions:
            total = 0.0
            for _ in range(self.simulations):
                total += self.rollout(state, action)
            scores[action] = total / self.simulations
        return scores

    def rollout(self, state: Any, first_action: str) -> float:
        sim_state = copy.deepcopy(state)
        self.env.step(sim_state, first_action)

        total_value = 0.0
        for step in range(self.depth):
            value = self.evaluate_state(sim_state)
            total_value += value * (0.9 ** step)
            next_action = self.sample_action(sim_state)
            self.env.step(sim_state, next_action)
        return total_value

    def evaluate_state(self, state: Any) -> float:
        hp = state.health / state.max_health if state.max_health else 0
        score = getattr(state, 'max_best', 0)
        risk = getattr(state, 'lethal_count', 0)
        return score * 2.0 + hp * 1.0 - risk * 0.7

    def sample_action(self, state: Any) -> str:
        actions = ["EXPLORE", "EXPLOIT", "MUTATE", "SEARCH_PROOF", "OPTIMIZE"]
        if state.health < state.max_health * 0.3:
            return "SURVIVE"
        if getattr(state, 'lethal_count', 0) > 5:
            return "REWRITE"
        return random.choice(actions)