# janus_genesis/module_integrator.py
"""
Модульный интегратор для динамического подключения расширений Януса.
Автоматически сканирует файловую систему, определяет зависимости,
обучается на успешных/неудачных интеграциях.
"""

import os
import sys
import importlib
import importlib.util
import inspect
import time
import json
import random
import logging
from collections import defaultdict, deque
from typing import Dict, List, Any, Optional, Type, Set, Tuple

logger = logging.getLogger("JANUS.INTEGRATOR")

# ========== БАЗОВЫЙ КЛАСС ДЛЯ МОДУЛЕЙ ==========
class BaseModule:
    """Базовый класс, от которого должны наследоваться модули."""
    def update(self):
        raise NotImplementedError

    def save_state(self):
        return {}

    def load_state(self, state):
        pass


class ModuleIntegrator:
    def __init__(self, root_dir: str = None, core=None, world=None, memory=None,
                 social_engine=None, language_engine=None, storyteller=None,
                 visionary=None, exclude_classes: Optional[List[str]] = None):
        self.root_dir = root_dir or os.getcwd()
        self.core = core
        self.world = world
        self.memory = memory
        self.social_engine = social_engine
        self.language_engine = language_engine
        self.storyteller = storyteller
        self.visionary = visionary
        self.exclude_classes = set(exclude_classes or ['NeedsSystem', 'PartySystem', 'BuffSystem', 'DiseaseSystem'])

        self.modules: Dict[str, Any] = {}               # имя -> объект модуля
        self.module_classes: Dict[str, Type] = {}       # имя -> класс
        self.module_files: Dict[str, str] = {}          # имя -> путь к файлу
        self.dependencies: Dict[str, Set[str]] = {}     # зависимости (модуль -> {зависимости})
        self.reverse_deps: Dict[str, Set[str]] = {}     # обратные зависимости

        self.integration_history: Dict[str, Dict] = {}  # история успехов/неудач
        self.module_order: List[str] = []               # порядок инициализации

        self._scan_modules()

    # ---------- Сканирование файловой системы ----------
    def _scan_modules(self):
        """Рекурсивно обходит root_dir, ищет Python-файлы и извлекает модули."""
        logger.info(f"Сканирование модулей в {self.root_dir}")
        for dirpath, _, filenames in os.walk(self.root_dir):
            for filename in filenames:
                if filename.endswith('.py') and not filename.startswith('__'):
                    full_path = os.path.join(dirpath, filename)
                    self._analyze_file(full_path)

    def _is_valid_module(self, cls: Type) -> bool:
        """Проверяет, подходит ли класс для регистрации как модуль."""
        # Проверяем, что это действительно класс
        if not inspect.isclass(cls):
            return False
        # Исключаем встроенные типы (dict, list и т.д.)
        if cls.__module__ in ('builtins', '__builtin__'):
            return False
        # Исключаем классы из списка
        if cls.__name__ in self.exclude_classes:
            logger.debug(f"Класс {cls.__name__} исключён по настройкам")
            return False
        # Должен быть метод update
        if not hasattr(cls, 'update') or not callable(cls.update):
            return False
        # Проверяем, что update не является встроенным методом (например, dict.update)
        update_method = getattr(cls, 'update')
        # Если это built-in function или method, то это не наш модуль
        if type(update_method).__name__ in ('builtin_function_or_method', 'method_descriptor'):
            logger.debug(f"Класс {cls.__name__} имеет встроенный update, пропускаем")
            return False
        # Проверяем сигнатуру update
        try:
            sig = inspect.signature(update_method)
        except ValueError:
            # Не удалось получить сигнатуру – скорее всего встроенный метод
            logger.debug(f"Не удалось получить сигнатуру update для {cls.__name__}, пропускаем")
            return False
        # Количество обязательных параметров (кроме self)
        required_params = 0
        for name, param in sig.parameters.items():
            if name == 'self':
                continue
            if param.default is inspect.Parameter.empty:
                required_params += 1
        # Если есть обязательные параметры, такой класс не может быть модулем (требует вызова с аргументами)
        if required_params > 0:
            logger.debug(f"Класс {cls.__name__} имеет update() с {required_params} обязательными параметрами, пропускаем")
            return False
        return True

    def _analyze_file(self, filepath: str):
        """Анализирует один файл: импортирует и ищет классы-модули."""
        rel_path = os.path.relpath(filepath, self.root_dir)
        module_name = os.path.splitext(rel_path.replace(os.sep, '.'))[0]
        try:
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if spec is None:
                return
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as e:
            logger.debug(f"Не удалось импортировать {filepath}: {e}")
            return

        for name, obj in inspect.getmembers(module, inspect.isclass):
            if self._is_valid_module(obj):
                # Если класс уже зарегистрирован, пропускаем (приоритет у первого)
                if name in self.module_classes:
                    logger.debug(f"Класс {name} уже зарегистрирован из другого файла")
                    continue
                self.module_classes[name] = obj
                self.module_files[name] = filepath
                # Определяем зависимости по аргументам конструктора
                deps = self._extract_dependencies(obj)
                self.dependencies[name] = deps
                logger.info(f"Найден модуль {name} в {filepath}")

    def _extract_dependencies(self, cls: Type) -> Set[str]:
        """Извлекает имена зависимостей из __init__ сигнатуры."""
        sig = inspect.signature(cls.__init__)
        deps = set()
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            # Если имя параметра совпадает с одним из полей интегратора (core, world, memory, ...)
            # или с именем другого модуля, считаем зависимостью.
            if param_name in ['core', 'world', 'memory', 'social_engine',
                              'language_engine', 'storyteller', 'visionary']:
                continue  # это не зависимости модулей, а системные компоненты
            # Если есть значение по умолчанию, возможно необязательная зависимость
            if param.default is inspect.Parameter.empty:
                deps.add(param_name)
        return deps

    # ---------- Определение порядка запуска ----------
    def _build_order(self):
        """Строит топологический порядок инициализации модулей."""
        # Копируем зависимости
        deps = {name: set(dep for dep in self.dependencies.get(name, []) if dep in self.module_classes)
                for name in self.module_classes}

        # Добавляем системные компоненты как "псевдо-модули" (они уже существуют)
        system_components = {'core', 'world', 'memory', 'social_engine', 'language_engine', 'storyteller', 'visionary'}
        for name, mod in self.module_classes.items():
            # Убираем зависимости, которые являются системными (они уже доступны)
            deps[name] = deps[name] - system_components

        # Топологическая сортировка (Kahn)
        in_degree = {name: 0 for name in self.module_classes}
        for name, deps_set in deps.items():
            for dep in deps_set:
                in_degree[name] += 1
                self.reverse_deps.setdefault(dep, set()).add(name)

        queue = deque([name for name, deg in in_degree.items() if deg == 0])
        order = []
        while queue:
            node = queue.popleft()
            order.append(node)
            for dependent in self.reverse_deps.get(node, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(order) != len(self.module_classes):
            # Есть цикл – попробуем разрешить, убрав некоторые зависимости
            logger.warning("Обнаружены циклические зависимости! Попытка разрешения.")
            order = list(self.module_classes.keys())

        self.module_order = order
        logger.info(f"Порядок модулей: {order}")

    # ---------- Инициализация модулей ----------
    def init_modules(self):
        """Инициализирует все найденные модули в правильном порядке."""
        if not self.module_classes:
            logger.info("Нет модулей для инициализации")
            return

        self._build_order()
        for name in self.module_order:
            self._init_module(name)

    def _init_module(self, name: str):
        """Инициализирует один модуль, передавая ему зависимости из контекста."""
        if name in self.modules:
            return

        cls = self.module_classes[name]
        # Определяем, какие аргументы нужны конструктору
        sig = inspect.signature(cls.__init__)
        kwargs = {}
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            # Сначала ищем в полях интегратора
            if hasattr(self, param_name):
                kwargs[param_name] = getattr(self, param_name)
            # Или среди уже инициализированных модулей
            elif param_name in self.modules:
                kwargs[param_name] = self.modules[param_name]
            # Или системные компоненты, которые переданы в конструктор интегратора
            elif param_name in ['core', 'world', 'memory', 'social_engine',
                                'language_engine', 'storyteller', 'visionary']:
                kwargs[param_name] = getattr(self, param_name)
            elif param.default is not inspect.Parameter.empty:
                continue  # опциональный параметр
            else:
                logger.warning(f"Для модуля {name} не найден обязательный аргумент {param_name}")
                return

        try:
            module = cls(**kwargs)
            # Помечаем модуль как созданный Янусом (для MonkeyPatcher)
            if not hasattr(module, '__janus_meta__'):
                module.__janus_meta__ = {'origin': 'janus', 'created': time.time()}
            self.modules[name] = module
            # Обновляем историю успеха
            self._record_integration(name, True)
            logger.info(f"Модуль {name} инициализирован")
        except Exception as e:
            logger.error(f"Ошибка инициализации модуля {name}: {e}", exc_info=True)
            self._record_integration(name, False)

    def register_module_class(self, name: str, module_class: Type, filepath: Optional[str] = None):
        """Регистрирует класс модуля вручную (для динамически созданных модулей)."""
        if name in self.module_classes:
            logger.warning(f"Модуль {name} уже зарегистрирован")
            return
        self.module_classes[name] = module_class
        self.module_files[name] = filepath or "manual"
        deps = self._extract_dependencies(module_class)
        self.dependencies[name] = deps
        logger.info(f"Зарегистрирован модуль {name}")

    def _record_integration(self, name: str, success: bool):
        """Записывает результат интеграции для обучения."""
        if name not in self.integration_history:
            self.integration_history[name] = {'success': 0, 'fail': 0, 'last_attempt': time.time()}
        if success:
            self.integration_history[name]['success'] += 1
        else:
            self.integration_history[name]['fail'] += 1
        self.integration_history[name]['last_attempt'] = time.time()

    # ---------- Обновление модулей ----------
    def update(self):
        """Вызывает update() у всех модулей (основной цикл)."""
        for name, mod in self.modules.items():
            if hasattr(mod, 'update'):
                try:
                    mod.update()
                except Exception as e:
                    logger.error(f"Ошибка в модуле {name}: {e}", exc_info=True)
                    self._record_integration(name, False)

    def update_modules(self):
        """Алиас для update()."""
        self.update()

    # ---------- Сохранение состояния ----------
    def save_state(self, path: str):
        """Сохраняет историю интеграции и состояние модулей."""
        state = {
            'history': self.integration_history,
            'modules': {}
        }
        for name, mod in self.modules.items():
            if hasattr(mod, 'save_state'):
                try:
                    state['modules'][name] = mod.save_state()
                except Exception as e:
                    logger.error(f"Ошибка сохранения состояния модуля {name}: {e}")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)

    def load_state(self, path: str):
        """Загружает историю и состояния модулей."""
        if not os.path.exists(path):
            return
        with open(path, 'r', encoding='utf-8') as f:
            state = json.load(f)
        self.integration_history = state.get('history', {})
        for name, mod_state in state.get('modules', {}).items():
            if name in self.modules and hasattr(self.modules[name], 'load_state'):
                try:
                    self.modules[name].load_state(mod_state)
                except Exception as e:
                    logger.error(f"Ошибка загрузки состояния модуля {name}: {e}")