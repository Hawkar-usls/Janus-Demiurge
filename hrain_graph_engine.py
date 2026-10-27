"""
HRAIN GRAPH ENGINE v1.2 — ЭВОЛЮЦИОННЫЙ ГРАФ С ПОВЕДЕНИЕМ PHYSARUM
- Поток энергии по рёбрам
- Хеббианское усиление активных путей
- Случайные мутации (exploration)
- Временнáя память (энергия затухает со временем)
- Активный подграф (внимание)
- Исправлено обновление last_used, auto_link, propagate_energy
"""

import json
import time
import random
import numpy as np
from collections import defaultdict, deque
from typing import Dict, List, Any, Optional, Tuple, Set

class HrainGraphEngine:
    def __init__(self, config: dict = None):
        self.config = {
            'edge_decay': 0.995,          # затухание веса за цикл
            'edge_reinforce': 0.05,        # усиление при использовании
            'energy_decay': 0.999,         # затухание энергии узла
            'node_energy_threshold': 0.01, # ниже этого удаляем узел
            'similarity_threshold': 0.3,   # порог для авто-связывания
            'cluster_similarity': 0.7,     # порог для кластеризации
            'max_cluster_size': 50,        # макс узлов в кластере до сжатия
            'compression_interval': 1000,  # тиков между сжатиями
            'max_nodes': 5000,             # hard admission limit; never delete old nodes
            'energy_flow_rate': 0.01,      # доля энергии, передаваемая за шаг
            'exploration_prob': 0.01,      # шанс случайной мутации
            'temporal_window': 100,        # окно для затухания энергии по времени
            ** (config or {})
        }
        self.nodes: Dict[str, Dict] = {}       # id -> {type, data, energy, last_used, cluster}
        self.edges: Dict[str, Dict] = {}       # "src->dst" -> {weight, direction, last_traversal}
        self.clusters: Dict[str, List[str]] = {}  # cluster_id -> [node_ids]
        self.node_counter = 0
        self.tick = 0
        self.pending_diffs: List[Dict] = []    # буфер для отправки diff на клиент
        # Counts only. Never persist node IDs or private content in safety reports.
        self.retention_holds = {
            'remove_node': 0, 'decay_edges': 0, 'decay_nodes': 0, 'max_nodes': 0
        }

    # -------------------- Утилиты --------------------
    def _node_id(self, base: str, suffix: str = "") -> str:
        self.node_counter += 1
        return f"{base}_{self.node_counter}{suffix}"

    def _edge_key(self, src: str, dst: str) -> str:
        return f"{src}->{dst}"

    def _record_diff(self, op: str, payload: Dict):
        self.pending_diffs.append({'op': op, 'payload': payload, 'tick': self.tick})

    # -------------------- Управление узлами --------------------
    def add_node(self, node_type: str, data: Dict, energy: float = 1.0) -> str:
        # Admit no new node beyond capacity rather than evicting persistent memory.
        # Exception occurs BEFORE counters, nodes or diffs are mutated.
        if len(self.nodes) >= int(self.config['max_nodes']):
            self.retention_holds['max_nodes'] += 1
            raise MemoryError("HRAIN_CAPACITY_REACHED_NO_EVICTION")
        node_id = self._node_id(node_type)
        self.nodes[node_id] = {
            'id': node_id,
            'type': node_type,
            'data': data,
            'energy': energy,
            'last_used': self.tick,
            'cluster': None
        }
        self._record_diff('node_add', {
            'id': node_id,
            'type': node_type,
            'data': data,
            'energy': energy
        })
        return node_id

    def remove_node(self, node_id: str):
        """Safety quarantine: no live-node deletion without an audited journal.

        Existing callers (including Maxwell and legacy cleanup) receive False
        and MUST NOT report a successful prune. This deliberate HOLD applies
        to explicit calls too; there is no config bypass for private memory.
        """
        if node_id in self.nodes:
            self.retention_holds['remove_node'] += 1
        return False

    # -------------------- Связи --------------------
    def add_edge(self, src: str, dst: str, direction: str = "bidir", weight: float = 1.0):
        key = self._edge_key(src, dst)
        if key in self.edges:
            self.edges[key]['weight'] += self.config['edge_reinforce']
            self.edges[key]['last_traversal'] = self.tick
        else:
            self.edges[key] = {
                'weight': weight,
                'direction': direction,
                'last_traversal': self.tick
            }
        # Обновляем время последнего использования узлов
        if src in self.nodes:
            self.nodes[src]['last_used'] = self.tick
        if dst in self.nodes:
            self.nodes[dst]['last_used'] = self.tick
        self._record_diff('edge_add', {
            'src': src,
            'dst': dst,
            'direction': direction,
            'weight': weight
        })

    # -------------------- Физика графа --------------------
    def decay_edges(self):
        """Затухание весов рёбер."""
        for key, edge in list(self.edges.items()):
            edge['weight'] *= self.config['edge_decay']
            if edge['weight'] < 0.01:
                # Keep the original relation, including provenance and direction.
                self.retention_holds['decay_edges'] += 1

    def decay_nodes(self):
        """Затухание энергии узлов."""
        for nid, node in list(self.nodes.items()):
            node['energy'] *= self.config['energy_decay']
            if node['energy'] < self.config['node_energy_threshold']:
                # Decay is permitted; removing persistent nodes is not.
                self.retention_holds['decay_nodes'] += 1

    def propagate_energy(self):
        """Поток энергии по рёбрам (Physarum)."""
        transfers = defaultdict(float)
        for key, edge in self.edges.items():
            src, dst = key.split('->')
            if src not in self.nodes or dst not in self.nodes:
                continue
            # Ограничиваем передаваемую энергию доступной энергией источника
            flow = min(self.nodes[src]['energy'],
                       self.nodes[src]['energy'] * edge['weight'] * self.config['energy_flow_rate'])
            if flow > 0:
                transfers[src] -= flow
                transfers[dst] += flow
        for nid, delta in transfers.items():
            if nid in self.nodes:
                self.nodes[nid]['energy'] = max(0.0, self.nodes[nid]['energy'] + delta)
                self.nodes[nid]['last_used'] = self.tick   # обновляем время активности

    def reinforce_active_paths(self):
        """Хеббианское усиление: если оба конца активны, усиливаем ребро."""
        for key, edge in self.edges.items():
            src, dst = key.split('->')
            if src in self.nodes and dst in self.nodes:
                if self.nodes[src]['energy'] > 0.5 and self.nodes[dst]['energy'] > 0.5:
                    edge['weight'] += self.config['edge_reinforce'] * 0.5
                    edge['last_traversal'] = self.tick

    def random_exploration(self):
        """Случайные мутации графа (поиск новых путей)."""
        if random.random() > self.config['exploration_prob'] or len(self.nodes) < 2:
            return
        ids = list(self.nodes.keys())
        a, b = random.sample(ids, 2)
        self.add_edge(a, b, 'explore', weight=random.uniform(0.1, 0.5))

    def temporal_decay(self):
        """Энергия узлов затухает со временем (забывание)."""
        for nid, node in self.nodes.items():
            age = self.tick - node['last_used']
            if age > 0:
                decay = (self.config['energy_decay'] ** min(age, self.config['temporal_window']))
                node['energy'] *= decay

    # -------------------- Авто-связывание (оптимизированное) --------------------
    def _node_similarity(self, n1: Dict, n2: Dict) -> float:
        d1 = n1['data']
        d2 = n2['data']
        purity_diff = abs(d1.get('purity', 0) - d2.get('purity', 0)) / 100.0
        temp_diff = abs(d1.get('temp', 0) - d2.get('temp', 0)) / 100.0
        agent_same = 1.0 if d1.get('agent_id') == d2.get('agent_id') else 0.0
        sim = (1 - min(1, purity_diff)) * 0.4 + (1 - min(1, temp_diff)) * 0.4 + agent_same * 0.2
        return sim

    def auto_link(self):
        """Создаёт связи между похожими узлами, используя выборку (O(N*M) вместо O(N²))."""
        node_ids = list(self.nodes.keys())
        if len(node_ids) < 2:
            return
        # Ограничиваем выборку для производительности
        sample_size = min(100, len(node_ids))
        sample_ids = random.sample(node_ids, sample_size)
        for i in range(len(sample_ids)):
            for j in range(i+1, len(sample_ids)):
                id1, id2 = sample_ids[i], sample_ids[j]
                n1, n2 = self.nodes[id1], self.nodes[id2]
                sim = self._node_similarity(n1, n2)
                if sim > self.config['similarity_threshold']:
                    key = self._edge_key(id1, id2)
                    if key not in self.edges:   # не спамим существующие
                        self.add_edge(id1, id2, 'bidir', weight=sim)

    # -------------------- Кластеризация и сжатие --------------------
    def compress_clusters(self):
        """Fail-closed legacy compaction quarantine (issue #342).

        The former implementation deleted every clustered node and all of its
        incident edges, including newly created meta/member relations.
        This public runtime entrypoint MUST NOT mutate the graph, even if
        invoked manually or by update() at compression_interval. A separate,
        owner-private lossless shadow is under evaluation; it is not a
        replacement for this gate or permission to destroy original nodes.
        """
        return {
            "status": "HOLD_LEGACY_DESTRUCTIVE_COMPRESSION",
            "production_use_authorized": False,
            "source_nodes": len(self.nodes),
            "source_edges": len(self.edges),
        }

    # -------------------- Активный подграф (внимание) --------------------
    def get_active_subgraph(self, top_k=50):
        """Возвращает самые энергетически насыщенные узлы."""
        sorted_nodes = sorted(self.nodes.items(), key=lambda x: x[1]['energy'], reverse=True)
        return dict(sorted_nodes[:top_k])

    # -------------------- NP-задачи --------------------
    def add_np_task(self, task_id: str, difficulty: float, solved: bool, agent_id: str = None):
        node_id = self.add_node('np_task', {'task_id': task_id, 'difficulty': difficulty, 'solved': solved})
        if solved:
            self.nodes[node_id]['energy'] += difficulty * 5
        else:
            self.nodes[node_id]['energy'] += difficulty * 1
        if agent_id and agent_id in self.nodes:
            self.add_edge(node_id, agent_id, 'task->agent', weight=1.0)
            if solved:
                self.add_edge(agent_id, node_id, 'agent->task_solved', weight=1.0)
        return node_id

    # -------------------- Основной цикл --------------------
    def update(self, events: List[Dict]) -> List[Dict]:
        """Принимает список новых событий, обновляет граф, возвращает diff."""
        # Reject an oversized event batch BEFORE modifying the graph or tick.
        # Existing graph copies are never truncated to make room.
        if len(self.nodes) + len(events) > int(self.config['max_nodes']):
            self.retention_holds['max_nodes'] += 1
            raise MemoryError("HRAIN_EVENT_BATCH_CAPACITY_HOLD")
        self.tick += 1
        # 1. Добавляем новые узлы из событий
        for ev in events:
            node_id = self.add_node(ev['type'], ev.get('data', {}))
            # Временная связь с предыдущим узлом (если есть)
            if len(self.nodes) > 1:
                last_node = list(self.nodes.keys())[-2]
                self.add_edge(last_node, node_id, 'temporal', weight=1.0)

        # 2. Применяем физическую динамику в правильном порядке
        self.decay_edges()
        self.decay_nodes()
        self.propagate_energy()
        self.reinforce_active_paths()
        self.random_exploration()
        self.auto_link()
        self.temporal_decay()

        # 3. Периодическое сжатие
        if self.tick % self.config['compression_interval'] == 0:
            self.compress_clusters()

        # 4. Never evict historical memory as an implementation of max_nodes.
        # Capacity is checked before adding an event batch and in add_node().

        # 5. Возвращаем накопленные diffs
        diffs = self.pending_diffs
        self.pending_diffs = []
        return diffs

    # -------------------- Сохранение / загрузка --------------------
    def get_full_state(self) -> Dict:
        return {
            'nodes': self.nodes,
            'edges': self.edges,
            'tick': self.tick,
            'node_counter': self.node_counter
        }

    def load_full_state(self, state: Dict):
        self.nodes = state['nodes']
        self.edges = state['edges']
        self.tick = state['tick']
        self.node_counter = state['node_counter']