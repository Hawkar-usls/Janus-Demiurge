# janus_genesis/np_task.py
"""
NP-задачи для Януса: 3-SAT, генерация серий, масштабирование.
Добавлена генерация задач в фазе перехода (4.26) и быстрая проверка.
"""

import random
import time
import numpy as np
from typing import List, Optional, Tuple, Dict, Any


class NPTask:
    """
    Генератор и верификатор 3-SAT задач.
    """
    def __init__(self, n_vars: int, n_clauses: int, phase_transition: bool = False):
        self.n_vars = n_vars
        self.n_clauses = n_clauses
        self.clauses = []
        if phase_transition:
            # Используем фиксированное отношение 4.26 для фазы перехода
            self.n_clauses = int(4.26 * n_vars)
        self._generate_random_sat()

    def _generate_random_sat(self):
        """Генерирует случайную 3-SAT формулу."""
        self.clauses = []
        for _ in range(self.n_clauses):
            literals = []
            for _ in range(3):
                var = random.randint(1, self.n_vars)
                neg = random.choice([True, False])
                literals.append((var, neg))
            self.clauses.append(literals)

    def check_solution(self, assignment: List[bool]) -> bool:
        """
        Проверяет, выполняет ли присваивание формулу.
        assignment: список из n_vars булевых значений (True = переменная истинна).
        """
        for clause in self.clauses:
            clause_satisfied = False
            for var, neg in clause:
                val = assignment[var - 1]
                if neg:
                    val = not val
                if val:
                    clause_satisfied = True
                    break
            if not clause_satisfied:
                return False
        return True

    def difficulty(self) -> float:
        """Оценочная сложность (отношение числа предложений к числу переменных)."""
        return self.n_clauses / max(1, self.n_vars)

    def to_dict(self) -> Dict:
        return {
            'type': '3-SAT',
            'n_vars': self.n_vars,
            'n_clauses': self.n_clauses,
            'clauses': self.clauses
        }

    @staticmethod
    def from_dict(data: Dict) -> 'NPTask':
        task = NPTask(data['n_vars'], data['n_clauses'])
        task.clauses = data['clauses']
        return task


def generate_series(sizes: List[int], n_tasks_per_size: int = 3, phase_transition: bool = False) -> List[NPTask]:
    """
    Генерирует серию 3-SAT задач для заданных размеров.
    Если phase_transition=True, используется отношение 4.26.
    """
    tasks = []
    for n_vars in sizes:
        if phase_transition:
            n_clauses = int(4.26 * n_vars)
        else:
            n_clauses = 3 * n_vars
        for _ in range(n_tasks_per_size):
            tasks.append(NPTask(n_vars, n_clauses, phase_transition=phase_transition))
    return tasks


def generate_adaptive_series(state, purity: float, current_difficulty: float = 1.0,
                             phase_transition: bool = False) -> List[NPTask]:
    """
    Генерирует серию задач с адаптивными размерами на основе прогресса.
    Если phase_transition=True, используется отношение 4.26.
    """
    base_sizes = [5, 8, 10, 12, 15]
    if current_difficulty > 2.0:
        base_sizes.extend([18, 20])
    elif current_difficulty > 1.5:
        base_sizes.extend([15, 18])
    elif current_difficulty < 0.5:
        base_sizes = [3, 5, 7]
    sizes = sorted(set(base_sizes))

    tasks = []
    for n_vars in sizes:
        if phase_transition:
            n_clauses = int(4.26 * n_vars)
        else:
            n_clauses = int(current_difficulty * n_vars)
        n_clauses = max(3, n_clauses)
        tasks.append(NPTask(n_vars, n_clauses, phase_transition=phase_transition))
    return tasks