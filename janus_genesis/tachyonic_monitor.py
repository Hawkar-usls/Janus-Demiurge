"""
Частотный мониторинг — отслеживает цифровой корень метрик и определяет моменты резонанса (777 Гц).
"""

from .filter_37 import digital_root

class TachyonicMonitor:
    def __init__(self, threshold_hits: int = 10):
        self.threshold_hits = threshold_hits
        self.resonance_hits = 0
        self.resonant = False

    def update(self, metric: float) -> bool:
        """
        Обновляет монитор новым значением метрики (score, loss, mi).
        Возвращает True, если достигнут резонанс (цифровой корень = 3 и накоплено пороговое число попаданий).
        """
        # Переводим метрику в условную частоту (можно просто взять целую часть после умножения)
        pseudo_freq = int(abs(metric * 1000))
        dr = digital_root(pseudo_freq)
        if dr == 3:
            self.resonance_hits += 1
            if self.resonance_hits >= self.threshold_hits and not self.resonant:
                self.resonant = True
                return True
        else:
            self.resonance_hits = max(0, self.resonance_hits - 1)
            self.resonant = False
        return False

    def reset(self):
        """Сброс состояния резонанса (после применения)."""
        self.resonance_hits = 0
        self.resonant = False