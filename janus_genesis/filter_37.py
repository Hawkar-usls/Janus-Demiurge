"""
Фильтр 37 — проверка резонанса гиперпараметров с гармониками Януса.
"""

def digital_root(n: int) -> int:
    """Вычисляет цифровой корень числа (1-9)."""
    if n == 0:
        return 0
    return 1 + (n - 1) % 9

def is_resonant(value: int) -> bool:
    """
    Проверяет, резонирует ли число с фильтром 37:
    - делится на 37
    - или его цифровой корень = 3
    """
    return (value % 37 == 0) or (digital_root(value) == 3)

def filter_hyperparams(config: dict, boost: float = 1.5, penalty: float = 0.8) -> dict:
    """
    Корректирует веса гиперпараметров, умножая их на коэффициент резонанса.
    Возвращает словарь с дополнительным полем 'resonance_weight'.
    """
    weight = 1.0
    for key, value in config.items():
        if key in ('n_embd', 'n_head', 'n_layer'):
            if is_resonant(value):
                weight *= boost
            else:
                weight *= penalty
    config['resonance_weight'] = min(weight, 2.0)  # ограничим сверху
    return config