# janus_genesis/monkey_patcher.py
"""
Манки-патчер для саморазвития модулей Януса.
Умеет улучшать только те модули, которые были созданы системой,
оценивать результат и обучаться на своих попытках.
"""

import os
import ast
import time
import random
import logging
import importlib
import inspect
import textwrap
from typing import Dict, List, Any, Optional, Set, Tuple
from collections import defaultdict, deque

logger = logging.getLogger("JANUS.MONKEY")

# ========== КОНСТАНТЫ ==========
PATCH_HISTORY_FILE = os.path.join("patches", "patch_history.json")
TEST_TIMEOUT = 5.0  # секунд на тест патча
MAX_PATCH_TRIALS = 10  # максимальное число попыток на модуль

# ========== БАЗОВЫЕ ПАТЧИ ==========
class BasePatch:
    """Базовый класс для патча."""
    name: str = "base"
    description: str = "Базовый патч (ничего не делает)"

    def apply(self, module) -> bool:
        """Применить патч к модулю. Вернуть True, если успешно."""
        return True

    def revert(self, module) -> bool:
        """Откатить патч."""
        return True


class OptimizeLoopPatch(BasePatch):
    """Оптимизирует циклы: заменяет for на while с локальными переменными."""
    name = "optimize_loops"
    description = "Замена for на while для ускорения"

    def apply(self, module):
        # Здесь реальный код патча: нужно модифицировать ast и перекомпилировать
        # Для примера – заглушка
        return True


class CacheResultsPatch(BasePatch):
    """Добавляет простое кэширование для методов, возвращающих одно и то же."""
    name = "cache_results"
    description = "Кэширование результатов методов"

    def apply(self, module):
        # Добавляет декоратор @lru_cache к методам без побочных эффектов
        # Заглушка
        return True


class ReduceComplexityPatch(BasePatch):
    """Упрощает сложные выражения."""
    name = "reduce_complexity"
    description = "Упрощение выражений"

    def apply(self, module):
        # ast-анализ и упрощение
        return True


# ========== ОСНОВНОЙ КЛАСС ==========
class MonkeyPatcher:
    def __init__(self, integrator, world, memory):
        """
        integrator: ModuleIntegrator (для доступа к модулям)
        world: объект мира (для получения метрик)
        memory: EvolutionaryMemory (для оценки успеха)
        """
        self.integrator = integrator
        self.world = world
        self.memory = memory
        self.patch_history = self._load_history()
        self.available_patches = [OptimizeLoopPatch(), CacheResultsPatch(), ReduceComplexityPatch()]
        self.patch_scores = defaultdict(lambda: 0.0)  # имя патча -> средний успех
        self.patch_attempts = defaultdict(int)        # количество попыток
        self.module_patch_log = {}                    # модуль -> последний применённый патч

    def _load_history(self) -> Dict:
        """Загружает историю патчей."""
        if os.path.exists(PATCH_HISTORY_FILE):
            try:
                import json
                with open(PATCH_HISTORY_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Ошибка загрузки истории патчей: {e}")
        return {}

    def _save_history(self):
        """Сохраняет историю патчей."""
        try:
            import json
            os.makedirs(os.path.dirname(PATCH_HISTORY_FILE), exist_ok=True)
            with open(PATCH_HISTORY_FILE, 'w') as f:
                json.dump(self.patch_history, f, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения истории патчей: {e}")

    def _is_janus_module(self, module) -> bool:
        """Проверяет, создан ли модуль системой."""
        # Ищем маркер в атрибутах модуля
        if hasattr(module, '__janus_meta__'):
            return module.__janus_meta__.get('origin') == 'janus'
        # Или в файле метаданных рядом
        module_file = inspect.getfile(module)
        meta_file = os.path.splitext(module_file)[0] + ".meta.json"
        if os.path.exists(meta_file):
            try:
                import json
                with open(meta_file, 'r') as f:
                    meta = json.load(f)
                return meta.get('origin') == 'janus'
            except:
                pass
        return False

    def _evaluate_module(self, module) -> float:
        """
        Оценивает модуль: возвращает метрику (чем выше, тем лучше).
        Можно использовать скорость работы, стабильность, влияние на score.
        """
        if not hasattr(module, 'update'):
            return 0.0

        # Простейшая оценка: время выполнения update()
        try:
            start = time.perf_counter()
            module.update()
            elapsed = time.perf_counter() - start
            # Штраф за время: чем быстрее, тем выше балл
            time_score = 1.0 / (1.0 + elapsed)
            # Бонус за стабильность (если нет исключений)
            stability_bonus = 0.5
            return time_score + stability_bonus
        except Exception as e:
            logger.warning(f"Ошибка при оценке модуля {module.__name__}: {e}")
            return 0.0

    def _apply_patch(self, module, patch) -> bool:
        """Применяет патч к модулю и возвращает True при успехе."""
        try:
            # Сохраняем оригинальный код
            module_file = inspect.getfile(module)
            with open(module_file, 'r', encoding='utf-8') as f:
                original_code = f.read()

            # Применяем патч (в реальности здесь нужно модифицировать код и перезагрузить)
            # Для примера – просто заглушка
            patch.apply(module)

            # Перезагружаем модуль
            importlib.reload(module)
            # Обновляем ссылку в интеграторе
            if module.__name__ in self.integrator.modules:
                self.integrator.modules[module.__name__] = module
            return True
        except Exception as e:
            logger.error(f"Ошибка применения патча {patch.name} к {module.__name__}: {e}")
            return False

    def _revert_patch(self, module, patch) -> bool:
        """Откатывает патч."""
        try:
            patch.revert(module)
            importlib.reload(module)
            if module.__name__ in self.integrator.modules:
                self.integrator.modules[module.__name__] = module
            return True
        except Exception as e:
            logger.error(f"Ошибка отката патча {patch.name} для {module.__name__}: {e}")
            return False

    def _select_patch(self, module) -> Optional[BasePatch]:
        """Выбирает лучший патч для модуля на основе истории."""
        # Если у модуля уже был успешный патч, можно попробовать его же или улучшить
        if module.__name__ in self.module_patch_log:
            last_patch_name = self.module_patch_log[module.__name__]
            # ищем патч с таким именем
            for p in self.available_patches:
                if p.name == last_patch_name:
                    # Если последний патч был успешен, можно его же и применить (или пробовать другой)
                    if random.random() < 0.3:
                        return p
        # Иначе выбираем случайный, но с весами по успешности
        total_weight = sum(self.patch_scores[p.name] for p in self.available_patches) + 1e-6
        if total_weight == 0:
            return random.choice(self.available_patches)
        probs = [(self.patch_scores[p.name] + 0.1) / total_weight for p in self.available_patches]
        return np.random.choice(self.available_patches, p=probs)

    def _record_patch_result(self, patch: BasePatch, module, success: bool, improvement: float):
        """Записывает результат патча для обучения."""
        key = f"{patch.name}_{module.__name__}"
        if key not in self.patch_history:
            self.patch_history[key] = {'attempts': 0, 'successes': 0, 'total_improvement': 0.0}
        rec = self.patch_history[key]
        rec['attempts'] += 1
        if success:
            rec['successes'] += 1
            rec['total_improvement'] += improvement
        # Обновляем общий рейтинг патча
        self.patch_scores[patch.name] = (self.patch_scores[patch.name] * self.patch_attempts[patch.name] +
                                          (improvement if success else -improvement)) / (self.patch_attempts[patch.name] + 1)
        self.patch_attempts[patch.name] += 1
        self._save_history()

    def patch_module(self, module) -> bool:
        """Пытается улучшить модуль, применяя лучший патч."""
        if not self._is_janus_module(module):
            logger.debug(f"Модуль {module.__name__} не помечен как созданный Янусом, пропускаем")
            return False

        # Оценка до патча
        before_score = self._evaluate_module(module)
        if before_score <= 0:
            logger.debug(f"Модуль {module.__name__} не поддаётся оценке, пропускаем")
            return False

        patch = self._select_patch(module)
        if not patch:
            return False

        logger.info(f"Применяем патч {patch.name} к модулю {module.__name__}")
        success = self._apply_patch(module, patch)
        if not success:
            self._record_patch_result(patch, module, False, 0.0)
            return False

        # Оценка после патча
        after_score = self._evaluate_module(module)
        improvement = after_score - before_score
        if improvement > 0:
            logger.info(f"Патч {patch.name} улучшил модуль {module.__name__} на {improvement:.3f}")
            self.module_patch_log[module.__name__] = patch.name
            self._record_patch_result(patch, module, True, improvement)
            return True
        else:
            logger.info(f"Патч {patch.name} не улучшил модуль {module.__name__} (изменение {improvement:.3f})")
            self._revert_patch(module, patch)
            self._record_patch_result(patch, module, False, improvement)
            return False

    def update(self):
        """Основной метод: периодически выбирает модули для патчинга."""
        if not self.integrator.modules:
            return

        # Сначала обновляем рейтинги патчей на основе общей истории (можно добавить обучение)
        # Простейшее обучение: чем выше средний успех, тем чаще патч будет выбираться
        for patch in self.available_patches:
            # Рассчитываем успешность из истории
            total = 0
            successes = 0
            for key, rec in self.patch_history.items():
                if key.startswith(patch.name + '_'):
                    total += rec['attempts']
                    successes += rec['successes']
            if total > 0:
                self.patch_scores[patch.name] = successes / total

        # Выбираем модуль для патча (можно случайный, можно наименее стабильный)
        modules = list(self.integrator.modules.values())
        candidate = random.choice(modules)

        # Проверяем, не слишком ли часто мы патчим этот модуль
        if candidate.__name__ in self.module_patch_log:
            # Если уже патчили и был успех, можно повторить через некоторое время
            # Здесь упрощённо: пропускаем, если последний патч был применён недавно
            if random.random() < 0.7:
                return

        self.patch_module(candidate)

    def save_state(self) -> Dict:
        """Сохраняет состояние для восстановления."""
        return {
            'patch_history': self.patch_history,
            'patch_scores': dict(self.patch_scores),
            'patch_attempts': dict(self.patch_attempts),
            'module_patch_log': self.module_patch_log
        }

    def load_state(self, state: Dict):
        """Загружает состояние."""
        self.patch_history = state.get('patch_history', {})
        self.patch_scores = defaultdict(float, state.get('patch_scores', {}))
        self.patch_attempts = defaultdict(int, state.get('patch_attempts', {}))
        self.module_patch_log = state.get('module_patch_log', {})