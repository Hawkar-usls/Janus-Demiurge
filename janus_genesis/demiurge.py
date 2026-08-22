# janus_genesis/demiurge.py
"""Demiurge meta-controller with cumulative spiral evolution.

Each analyze/decide/apply pass is a new turn. Recent windows may stay bounded
for control math, but older turns are archived instead of silently removed.
"""

import logging
from typing import Any, Dict, Optional

import numpy as np

from spiral_evolution import PreservingWindow, SpiralLedger

logger = logging.getLogger("JANUS.DEMIURGE")


class Demiurge:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {
            'progress_threshold_low': 0.3,
            'progress_threshold_high': 0.8,
            'diversity_threshold_low': 0.2,
            'diversity_threshold_high': 0.8,
            'temp_threshold_high': 75.0,
            'temp_threshold_low': 50.0,
            'stress_threshold': 0.7,
            'convergence_window': 50,
            'np_reward_scale_factor': 0.2,
            'np_chance_factor': 0.1,
            'mutation_rate_factor': 0.05,
            'social_learning_factor': 0.1,
            'raid_frequency_factor': 0.05,
            'market_frequency_factor': 0.05,
            'spawn_difficulty_factor': 0.1,
            'batch_size_factor': 0.2,
            'temperature_target_factor': 5.0,
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
        self.last_analysis = None
        self.history = PreservingWindow(100)
        self.np_progress_history = PreservingWindow(50)
        self.convergence_counter = 0
        self.spiral = SpiralLedger("JANUS_DEMIURGE_META_CONTROLLER")
        self.pending_analysis = None
        self.pending_decisions = None

    @property
    def spiral_turn(self) -> int:
        return self.spiral.next_turn

    def analyze(self, metrics: Dict[str, Any], world, rpg_state, memory) -> Dict[str, Any]:
        purity = metrics.get('purity_score', 0.0)
        temp_f = metrics.get('temp_f', 120.0)
        entropy = metrics.get('hw_entropy', 0.005)
        score = metrics.get('last_score', 0.0)
        val_loss = metrics.get('val_loss', 10.0)
        mi = metrics.get('mi', 0.0)
        gap = metrics.get('gap', 0.0)
        np_progress = self._compute_np_progress(rpg_state, memory)
        diversity = self._compute_diversity(world)
        convergence = self._compute_convergence(memory)
        thermal_stress = max(0.0, min(1.0, (temp_f - self.config['temp_threshold_low']) /
                                      (self.config['temp_threshold_high'] - self.config['temp_threshold_low'])))
        janus_stress = 1.0 - (rpg_state.health / rpg_state.max_health) if rpg_state.max_health else 0.0
        analysis = {
            'spiral_turn': self.spiral_turn,
            'purity': purity,
            'temperature_f': temp_f,
            'entropy': entropy,
            'score': score,
            'loss': val_loss,
            'mi': mi,
            'gap': gap,
            'gpu_load': metrics.get('gpu_load', 0.0),
            'cpu_load': metrics.get('cpu_load', 0.0),
            'gaming_mode': metrics.get('gaming_mode', False),
            'np_progress': np_progress,
            'diversity': diversity,
            'convergence': convergence,
            'thermal_stress': thermal_stress,
            'janus_stress': janus_stress,
            'efficiency': score / (val_loss + 1e-6),
            'research_level': (mi - gap) / 2.0,
        }
        self.last_analysis = analysis
        self.pending_analysis = analysis
        self.history.append(analysis)
        if np_progress is not None:
            self.np_progress_history.append(np_progress)
        return analysis

    def _compute_np_progress(self, rpg_state, memory) -> Optional[float]:
        if hasattr(rpg_state, 'np_series_results') and rpg_state.np_series_results:
            series = rpg_state.np_series_results
            return sum(1 for r in series if r['solved']) / len(series)
        if hasattr(memory, 'complexity_trend') and memory.complexity_trend:
            trend = memory.complexity_trend
            current = trend[-1]
            max_diff = max(trend)
            return current / max_diff if max_diff > 0 else 0.5
        return None

    def _compute_diversity(self, world) -> float:
        if not getattr(world, 'population', None):
            return 0.0
        keys = ['lr', 'gain', 'temperature', 'n_embd', 'n_head', 'n_layer']
        all_vals = {k: [] for k in keys}
        for agent in world.population:
            for key in keys:
                if key in agent.base_config:
                    all_vals[key].append(agent.base_config[key])
        diversities = []
        for key, vals in all_vals.items():
            if len(vals) <= 1:
                continue
            arr = np.array(vals, dtype=float)
            if key == 'lr':
                arr = np.log10(arr + 1e-8)
            elif key in ['n_embd', 'n_head', 'n_layer']:
                arr = arr / 100.0
            diversities.append(min(1.0, float(np.std(arr)) / 0.5))
        return float(np.mean(diversities)) if diversities else 0.0

    def _compute_convergence(self, memory) -> float:
        if hasattr(memory, 'convergence_cycle') and memory.convergence_cycle is not None:
            return 1.0
        if not hasattr(memory, 'history') or len(memory.history) <= 20:
            return 0.0
        recent = [h for h in memory.history if isinstance(h.get('score'), (int, float)) and h['score'] > -float('inf')][-20:]
        keys = ['lr', 'gain', 'temperature', 'n_embd', 'n_head', 'n_layer']
        vectors = []
        for record in recent:
            vec = []
            for key in keys:
                if key not in record:
                    continue
                value = record[key]
                if key == 'lr':
                    value = np.log10(value + 1e-8)
                elif key in ['n_embd', 'n_head', 'n_layer']:
                    value = value / 100.0
                vec.append(value)
            if vec:
                vectors.append(vec)
        if len(vectors) <= 1:
            return 0.0
        distances = [np.linalg.norm(np.array(vectors[i]) - np.array(vectors[j]))
                     for i in range(len(vectors)) for j in range(i + 1, len(vectors))]
        return 1.0 - min(1.0, float(np.mean(distances)) / 0.5) if distances else 0.0

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
                decisions['np_reward_mult'] = min(self.config['max_np_reward_mult'], 1.0 + self.config['np_reward_scale_factor'])
                decisions['np_chance'] = min(self.config['max_np_chance'], self._get_current_np_chance() + self.config['np_chance_factor'])
            elif np_progress > self.config['progress_threshold_high']:
                decisions['np_reward_mult'] = max(self.config['min_np_reward_mult'], 1.0 - self.config['np_reward_scale_factor'])
                decisions['np_chance'] = max(self.config['min_np_chance'], self._get_current_np_chance() - self.config['np_chance_factor'] * 0.5)

        diversity = analysis.get('diversity', 0.5)
        if diversity < self.config['diversity_threshold_low']:
            decisions['mutation_rate'] = min(self.config['max_mutation_rate'], self._get_current_mutation_rate() + self.config['mutation_rate_factor'])
            decisions['social_learning_rate'] = min(self.config['max_social_learning'], self._get_current_social_learning() + self.config['social_learning_factor'])
        elif diversity > self.config['diversity_threshold_high']:
            decisions['mutation_rate'] = max(self.config['min_mutation_rate'], self._get_current_mutation_rate() - self.config['mutation_rate_factor'])

        efficiency = analysis.get('efficiency', 1.0)
        research_level = analysis.get('research_level', 0.0)
        if efficiency > 2.0 and research_level > 0.5:
            decisions['raid_chance'] = min(self.config['max_raid_chance'], self._get_current_raid_chance() + self.config['raid_frequency_factor'])
            decisions['market_chance'] = min(self.config['max_market_chance'], self._get_current_market_chance() + self.config['market_frequency_factor'])
        elif efficiency < 0.5:
            decisions['raid_chance'] = max(self.config['min_raid_chance'], self._get_current_raid_chance() - self.config['raid_frequency_factor'])
            decisions['market_chance'] = max(self.config['min_market_chance'], self._get_current_market_chance() - self.config['market_frequency_factor'])

        if analysis.get('thermal_stress', 0.0) > 0.7 or analysis.get('janus_stress', 0.0) > 0.7:
            decisions['batch_size'] = int(max(self.config['min_batch_size'], self._get_current_batch_size() * (1 - self.config['batch_size_factor'])))
            decisions['target_temperature'] = min(self.config['max_target_temp'], self._get_current_target_temp() + self.config['temperature_target_factor'])
        elif analysis.get('thermal_stress', 0.0) < 0.2 and analysis.get('janus_stress', 0.0) < 0.2:
            decisions['batch_size'] = int(min(self.config['max_batch_size'], self._get_current_batch_size() * (1 + self.config['batch_size_factor'])))

        purity = analysis.get('purity', 0.0)
        if purity > 50.0:
            decisions['reward_scale'] = 1.05
        elif purity < 10.0:
            decisions['reward_scale'] = 0.95
        self.pending_decisions = {k: v for k, v in decisions.items() if v is not None}
        return self.pending_decisions

    def _get_current_np_chance(self) -> float:
        try:
            from genesis_protocol import GENESIS_CONFIG
            return GENESIS_CONFIG.get('np_task_chance', 0.2)
        except ImportError:
            return 0.2

    def _get_current_mutation_rate(self) -> float:
        return 0.15

    def _get_current_social_learning(self) -> float:
        return 0.1

    def _get_current_raid_chance(self) -> float:
        return 0.05

    def _get_current_market_chance(self) -> float:
        return 0.05

    def _get_current_batch_size(self) -> int:
        return 128

    def _get_current_target_temp(self) -> float:
        return 55.0

    def apply(self, decisions: Dict[str, Any], world, rpg_state):
        before = {
            'np_reward_mult': getattr(rpg_state, 'np_reward_mult', None),
            'raid_chance': getattr(world, 'raid_chance_override', None),
            'market_chance': getattr(world, 'market_chance_override', None),
        }
        if 'np_reward_mult' in decisions:
            rpg_state.np_reward_mult = decisions['np_reward_mult']
        if 'np_chance' in decisions:
            try:
                import genesis_protocol
                genesis_protocol.GENESIS_CONFIG['np_task_chance'] = decisions['np_chance']
            except ImportError:
                pass
        if 'mutation_rate' in decisions and hasattr(world, 'evolutionary_memory') and hasattr(world.evolutionary_memory, 'mutation_rate'):
            world.evolutionary_memory.mutation_rate = decisions['mutation_rate']
        if 'social_learning_rate' in decisions and hasattr(world, 'social_engine'):
            world.social_engine.params['observation_chance'] = decisions['social_learning_rate']
        if 'raid_chance' in decisions:
            world.raid_chance_override = decisions['raid_chance']
        if 'market_chance' in decisions:
            world.market_chance_override = decisions['market_chance']
        if 'batch_size' in decisions:
            rpg_state.demiurge_batch_size = decisions['batch_size']
        if 'target_temperature' in decisions and hasattr(world, 'thermal_controller'):
            world.thermal_controller.target_temp = decisions['target_temperature']
        if 'reward_scale' in decisions:
            rpg_state.demiurge_reward_scale = decisions['reward_scale']

        after = {
            'np_reward_mult': getattr(rpg_state, 'np_reward_mult', None),
            'raid_chance': getattr(world, 'raid_chance_override', None),
            'market_chance': getattr(world, 'market_chance_override', None),
        }
        lesson = "Applied measured adaptation; retain this turn as ancestry for the next decision."
        turn = self.spiral.ascend(
            state_before={'analysis': self.pending_analysis, 'control': before},
            candidate_state={'decisions': decisions},
            active_state_after={'control': after},
            lessons=[lesson],
            constraints=["NO_RESET_TO_PREVIOUS_TURN_WITHOUT_EXPLICIT_ROLLBACK_RECEIPT"],
            promoted=True,
        )
        logger.info("🌀 Демиург ASCEND turn=%s fingerprint=%s", turn.turn, turn.fingerprint[:12])
        return turn.to_dict()
