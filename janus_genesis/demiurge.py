# janus_genesis/demiurge.py
"""
Модуль Демиурга — мета-управление миром Genesis.
Анализирует состояние и корректирует параметры для ускорения поиска P=NP.
"""

import logging
import numpy as np
from typing import Dict, Any, Optional, List

logger = logging.getLogger("JANUS.DEMIURGE")

class Demiurge:
    """
    Демиург — мета-алгоритм, управляющий параметрами мира и эволюции.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Инициализация Демиурга с конфигурацией по умолчанию.
        """
        self.config = config or {
            # Пороги для срабатывания
            'progress_threshold_low': 0.3,
            'progress_threshold_high': 0.8,
            'diversity_threshold_low': 0.2,
            'diversity_threshold_high': 0.8,
            'temp_threshold_high': 75.0,
            'temp_threshold_low': 50.0,
            'stress_threshold': 0.7,
            'convergence_window': 50,
            # Коэффициенты изменения параметров
            'np_reward_scale_factor': 0.2,
            'np_chance_factor': 0.1,
            'mutation_rate_factor': 0.05,
            'social_learning_factor': 0.1,
            'raid_frequency_factor': 0.05,
            'market_frequency_factor': 0.05,
            'spawn_difficulty_factor': 0.1,
            'batch_size_factor': 0.2,
            'temperature_target_factor': 5.0,
            # Ограничения
            'min_np_reward_mult': 0.5,
            'max_np_reward_mult': 2.0,
            'min_np_chance': 0.05,
            'max_np_chance': 0.5,
            'min_mutation_rate': 0.05,
            'max_mutation_rate': 0.5,
            'min_social_learning': 0.05,
            'max_social_learning': 0.5,
            'min_raid_chance': 0.01,
            'max_raid_chance': 0.15,
            'min_market_chance': 0.01,
            'max_market_chance': 0.15,
            'min_batch_size': 16,
            'max_batch_size': 512,
            'min_target_temp': 40.0,
            'max_target_temp': 80.0,
        }

        # Состояние Демиурга
        self.last_analysis = None
        self.history = []
        self.convergence_counter = 0
        self.np_progress_history = []

    def analyze(self, metrics: Dict[str, Any], world, rpg_state, memory) -> Dict[str, Any]:
        """
        Анализирует текущее состояние и возвращает словарь с метриками.
        """
        purity = metrics.get('purity_score', 0.0)
        temp_f = metrics.get('temp_f', 120.0)
        entropy = metrics.get('hw_entropy', 0.005)
        score = metrics.get('last_score', 0.0) if 'last_score' in metrics else 0.0
        val_loss = metrics.get('val_loss', 10.0)
        mi = metrics.get('mi', 0.0)
        gap = metrics.get('gap', 0.0)
        gpu_load = metrics.get('gpu_load', 0.0)
        cpu_load = metrics.get('cpu_load', 0.0)
        gaming_mode = metrics.get('gaming_mode', False)

        np_progress = self._compute_np_progress(rpg_state, memory)
        diversity = self._compute_diversity(world)
        convergence = self._compute_convergence(memory)

        thermal_stress = max(0.0, min(1.0, (temp_f - self.config['temp_threshold_low']) /
                                      (self.config['temp_threshold_high'] - self.config['temp_threshold_low'])))
        janus_stress = 1.0 - (rpg_state.health / rpg_state.max_health) if rpg_state.max_health else 0.0
        efficiency = score / (val_loss + 1e-6)
        research_level = (mi - gap) / 2.0

        analysis = {
            'purity': purity,
            'temperature_f': temp_f,
            'entropy': entropy,
            'score': score,
            'loss': val_loss,
            'mi': mi,
            'gap': gap,
            'gpu_load': gpu_load,
            'cpu_load': cpu_load,
            'gaming_mode': gaming_mode,
            'np_progress': np_progress,
            'diversity': diversity,
            'convergence': convergence,
            'thermal_stress': thermal_stress,
            'janus_stress': janus_stress,
            'efficiency': efficiency,
            'research_level': research_level,
        }

        self.last_analysis = analysis
        self.history.append(analysis)
        if len(self.history) > 100:
            self.history.pop(0)

        if np_progress is not None:
            self.np_progress_history.append(np_progress)
            if len(self.np_progress_history) > 50:
                self.np_progress_history.pop(0)

        return analysis

    def _compute_np_progress(self, rpg_state, memory) -> Optional[float]:
        if hasattr(rpg_state, 'np_series_results') and rpg_state.np_series_results:
            series = rpg_state.np_series_results
            solved = sum(1 for r in series if r['solved'])
            if series:
                return solved / len(series)
        elif hasattr(memory, 'complexity_trend') and memory.complexity_trend:
            trend = memory.complexity_trend
            if trend:
                current = trend[-1] if trend else 1.0
                max_diff = max(trend) if trend else 1.0
                return current / max_diff if max_diff > 0 else 0.5
        return None

    def _compute_diversity(self, world) -> float:
        if not world.population:
            return 0.0
        keys = ['lr', 'gain', 'temperature', 'n_embd', 'n_head', 'n_layer']
        all_vals = {k: [] for k in keys}
        for agent in world.population:
            cfg = agent.base_config
            for k in keys:
                if k in cfg:
                    all_vals[k].append(cfg[k])
        diversities = []
        for k, vals in all_vals.items():
            if len(vals) > 1:
                if k in ['lr', 'gain', 'temperature']:
                    if k == 'lr':
                        vals = np.log10(np.array(vals) + 1e-8)
                    else:
                        vals = np.array(vals)
                else:
                    vals = np.array(vals) / 100.0
                std = np.std(vals)
                diversities.append(min(1.0, std / 0.5))
        if diversities:
            return np.mean(diversities)
        return 0.0

    def _compute_convergence(self, memory) -> float:
        if hasattr(memory, 'convergence_cycle') and memory.convergence_cycle is not None:
            return 1.0
        if hasattr(memory, 'history') and len(memory.history) > 20:
            recent = [h for h in memory.history if isinstance(h.get('score'), (int, float)) and h['score'] > -float('inf')][-20:]
            if len(recent) > 1:
                keys = ['lr', 'gain', 'temperature', 'n_embd', 'n_head', 'n_layer']
                vectors = []
                for h in recent:
                    vec = []
                    for k in keys:
                        if k in h:
                            val = h[k]
                            if k == 'lr':
                                val = np.log10(val + 1e-8)
                            elif k in ['n_embd', 'n_head', 'n_layer']:
                                val = val / 100.0
                            vec.append(val)
                    if vec:
                        vectors.append(vec)
                if vectors:
                    vectors = np.array(vectors)
                    distances = []
                    for i in range(len(vectors)):
                        for j in range(i+1, len(vectors)):
                            dist = np.linalg.norm(vectors[i] - vectors[j])
                            distances.append(dist)
                    avg_dist = np.mean(distances) if distances else 1.0
                    return 1.0 - min(1.0, avg_dist / 0.5)
        return 0.0

    def decide(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        decisions = {
            'np_reward_mult': 1.0,
            'np_chance': None,
            'mutation_rate': None,
            'social_learning_rate': None,
            'raid_chance': None,
            'market_chance': None,
            'spawn_difficulty': None,
            'batch_size': None,
            'target_temperature': None,
            'agent_spawn_rate': None,
            'reward_scale': 1.0,
        }

        np_progress = analysis.get('np_progress')
        if np_progress is not None:
            if np_progress < self.config['progress_threshold_low']:
                decisions['np_reward_mult'] = min(self.config['max_np_reward_mult'],
                                                  decisions['np_reward_mult'] + self.config['np_reward_scale_factor'])
                current_chance = self._get_current_np_chance()
                new_chance = min(self.config['max_np_chance'],
                                 current_chance + self.config['np_chance_factor'])
                decisions['np_chance'] = new_chance
                logger.info(f"Демиург: низкий прогресс NP ({np_progress:.2f}) → увеличиваем награду и частоту задач")
            elif np_progress > self.config['progress_threshold_high']:
                decisions['np_reward_mult'] = max(self.config['min_np_reward_mult'],
                                                  decisions['np_reward_mult'] - self.config['np_reward_scale_factor'])
                current_chance = self._get_current_np_chance()
                new_chance = max(self.config['min_np_chance'],
                                 current_chance - self.config['np_chance_factor'] * 0.5)
                decisions['np_chance'] = new_chance
                logger.info(f"Демиург: высокий прогресс NP ({np_progress:.2f}) → уменьшаем награду, сложность остаётся")

        diversity = analysis.get('diversity', 0.5)
        if diversity < self.config['diversity_threshold_low']:
            decisions['mutation_rate'] = self._get_current_mutation_rate() + self.config['mutation_rate_factor']
            decisions['mutation_rate'] = min(self.config['max_mutation_rate'], decisions['mutation_rate'])
            decisions['social_learning_rate'] = self._get_current_social_learning() + self.config['social_learning_factor']
            decisions['social_learning_rate'] = min(self.config['max_social_learning'], decisions['social_learning_rate'])
            logger.info(f"Демиург: низкое разнообразие ({diversity:.2f}) → увеличиваем мутации и соц. обучение")
        elif diversity > self.config['diversity_threshold_high']:
            decisions['mutation_rate'] = self._get_current_mutation_rate() - self.config['mutation_rate_factor']
            decisions['mutation_rate'] = max(self.config['min_mutation_rate'], decisions['mutation_rate'])
            logger.info(f"Демиург: высокое разнообразие ({diversity:.2f}) → уменьшаем мутации")

        efficiency = analysis.get('efficiency', 1.0)
        research_level = analysis.get('research_level', 0.0)
        if efficiency > 2.0 and research_level > 0.5:
            decisions['raid_chance'] = self._get_current_raid_chance() + self.config['raid_frequency_factor']
            decisions['raid_chance'] = min(self.config['max_raid_chance'], decisions['raid_chance'])
            decisions['market_chance'] = self._get_current_market_chance() + self.config['market_frequency_factor']
            decisions['market_chance'] = min(self.config['max_market_chance'], decisions['market_chance'])
            logger.info(f"Демиург: высокая эффективность ({efficiency:.2f}) → увеличиваем частоту рейдов и рынка")
        elif efficiency < 0.5:
            decisions['raid_chance'] = self._get_current_raid_chance() - self.config['raid_frequency_factor']
            decisions['raid_chance'] = max(self.config['min_raid_chance'], decisions['raid_chance'])
            decisions['market_chance'] = self._get_current_market_chance() - self.config['market_frequency_factor']
            decisions['market_chance'] = max(self.config['min_market_chance'], decisions['market_chance'])
            logger.info(f"Демиург: низкая эффективность ({efficiency:.2f}) → уменьшаем частоту рейдов и рынка")

        thermal_stress = analysis.get('thermal_stress', 0.0)
        janus_stress = analysis.get('janus_stress', 0.0)
        if thermal_stress > 0.7 or janus_stress > 0.7:
            current_batch = self._get_current_batch_size()
            new_batch = max(self.config['min_batch_size'],
                            current_batch * (1 - self.config['batch_size_factor']))
            decisions['batch_size'] = int(new_batch)
            current_target_temp = self._get_current_target_temp()
            new_target_temp = min(self.config['max_target_temp'],
                                  current_target_temp + self.config['temperature_target_factor'])
            decisions['target_temperature'] = new_target_temp
            logger.info(f"Демиург: перегрев/стресс → уменьшаем batch до {new_batch}, повышаем целевую температуру")
        elif thermal_stress < 0.2 and janus_stress < 0.2:
            current_batch = self._get_current_batch_size()
            new_batch = min(self.config['max_batch_size'],
                            current_batch * (1 + self.config['batch_size_factor']))
            decisions['batch_size'] = int(new_batch)
            logger.info(f"Демиург: низкая нагрузка → увеличиваем batch до {new_batch}")

        purity = analysis.get('purity', 0.0)
        if purity > 50.0:
            decisions['reward_scale'] = min(2.0, decisions['reward_scale'] + 0.05)
            logger.info(f"Демиург: высокая чистота ({purity:.1f}) → увеличиваем награду")
        elif purity < 10.0:
            decisions['reward_scale'] = max(0.5, decisions['reward_scale'] - 0.05)
            logger.info(f"Демиург: низкая чистота ({purity:.1f}) → уменьшаем награду")

        decisions = {k: v for k, v in decisions.items() if v is not None}
        return decisions

    def _get_current_np_chance(self) -> float:
        try:
            from genesis_protocol import GENESIS_CONFIG
            return GENESIS_CONFIG.get('np_task_chance', 0.2)
        except ImportError:
            return 0.2

    def _get_current_mutation_rate(self) -> float:
        return 0.15  # placeholder

    def _get_current_social_learning(self) -> float:
        return 0.1  # placeholder

    def _get_current_raid_chance(self) -> float:
        return 0.05

    def _get_current_market_chance(self) -> float:
        return 0.05

    def _get_current_batch_size(self) -> int:
        return 128  # placeholder

    def _get_current_target_temp(self) -> float:
        return 55.0

    def apply(self, decisions: Dict[str, Any], world, rpg_state):
        if 'np_reward_mult' in decisions:
            rpg_state.np_reward_mult = decisions['np_reward_mult']
            logger.info(f"Демиург: установлен множитель награды NP = {decisions['np_reward_mult']:.2f}")
        if 'np_chance' in decisions:
            try:
                import genesis_protocol
                genesis_protocol.GENESIS_CONFIG['np_task_chance'] = decisions['np_chance']
                logger.info(f"Демиург: установлен шанс NP-задачи = {decisions['np_chance']:.3f}")
            except ImportError:
                pass

        if 'mutation_rate' in decisions:
            if hasattr(world, 'evolutionary_memory') and hasattr(world.evolutionary_memory, 'mutation_rate'):
                world.evolutionary_memory.mutation_rate = decisions['mutation_rate']
                logger.info(f"Демиург: установлена скорость мутаций = {decisions['mutation_rate']:.3f}")
        if 'social_learning_rate' in decisions:
            if hasattr(world, 'social_engine'):
                world.social_engine.params['observation_chance'] = decisions['social_learning_rate']
                logger.info(f"Демиург: установлена вероятность соц. обучения = {decisions['social_learning_rate']:.3f}")

        if 'raid_chance' in decisions:
            world.raid_chance_override = decisions['raid_chance']
            logger.info(f"Демиург: установлен шанс рейда = {decisions['raid_chance']:.3f}")
        if 'market_chance' in decisions:
            world.market_chance_override = decisions['market_chance']
            logger.info(f"Демиург: установлен шанс рыночного события = {decisions['market_chance']:.3f}")

        if 'batch_size' in decisions:
            rpg_state.demiurge_batch_size = decisions['batch_size']
            logger.info(f"Демиург: рекомендованный batch size = {decisions['batch_size']}")
        if 'target_temperature' in decisions:
            if hasattr(world, 'thermal_controller'):
                world.thermal_controller.target_temp = decisions['target_temperature']
                logger.info(f"Демиург: установлена целевая температура = {decisions['target_temperature']:.1f}°C")

        if 'reward_scale' in decisions:
            rpg_state.demiurge_reward_scale = decisions['reward_scale']
            logger.info(f"Демиург: установлен множитель награды = {decisions['reward_scale']:.2f}")