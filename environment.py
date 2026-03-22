import torch
import numpy as np
from config import VOCAB_SIZE, DEVICE
from data_loader import load_real_data

class DemiurgeEnvironment:
    def __init__(self, registry_params=None):
        self.complexity_level = 1
        self.score_window = []
        self.seq_len = 64
        self.registry_params = registry_params
        # ВКЛЮЧАЕМ РЕАЛЬНЫЕ ДАННЫЕ (убедись, что файл device_data.json существует)
        self.use_real_data = True

        # Параметры синтетической генерации (изотопы)
        self.num_states = 7
        self.transitions = None
        self.starts = None
        self.lengths = None
        self.spike_prob = 0.05
        self.collapse_prob = 0.02

        if registry_params and 'emulation_parameters' in registry_params:
            params = registry_params['emulation_parameters']
            isotopes = params.get('isotopes', [])
            if len(isotopes) == self.num_states:
                self.starts = torch.tensor([iso['range'][0] for iso in isotopes], device=DEVICE)
                ends = torch.tensor([iso['range'][1] for iso in isotopes], device=DEVICE)
                self.lengths = ends - self.starts + 1
                trans_dict = params.get('transition_probabilities', {})
                trans_list = [
                    trans_dict.get('from_neutron', [1/7]*7),
                    trans_dict.get('from_stable', [1/7]*7),
                    trans_dict.get('from_unstable', [1/7]*7),
                    trans_dict.get('from_fragment', [1/7]*7),
                    trans_dict.get('from_hydrogen', [1/7]*7),
                    trans_dict.get('from_strontium', [1/7]*7),
                    trans_dict.get('from_plutonium', [1/7]*7)
                ]
                self.transitions = torch.tensor(trans_list, device=DEVICE, dtype=torch.float32)

    def update_complexity(self, current_score):
        self.score_window.append(current_score)
        if len(self.score_window) > 5:
            self.score_window.pop(0)
        if len(self.score_window) == 5:
            delta = self.score_window[-1] - self.score_window[0]
            if delta > 0.05:
                self.complexity_level += 1
            elif delta < -0.05:
                self.complexity_level = max(1, self.complexity_level - 1)

    def generate_tensors(self, num_sequences):
        if self.use_real_data:
            try:
                seq_list, device_stats = load_real_data(num_sequences=num_sequences, seq_len=self.seq_len)
                # seq_list — список списков целых чисел (токенов)
                # Преобразуем в тензор и сразу обрежем до допустимого диапазона
                data = torch.tensor(seq_list, dtype=torch.long, device=DEVICE)
                # Проверяем, нет ли значений вне диапазона
                if data.min() < 0 or data.max() >= VOCAB_SIZE:
                    print(f"[WARNING] Реальные данные вне словаря: min={data.min()}, max={data.max()}. Обрезаем.")
                    data = data.clamp(0, VOCAB_SIZE-1)
                # Дополнительная проверка: если после обрезания всё ещё есть значения >= VOCAB_SIZE (быть не должно, но на всякий случай)
                if data.max() >= VOCAB_SIZE:
                    print(f"[ERROR] После обрезания данные всё ещё содержат {data.max()} >= VOCAB_SIZE. Принудительно устанавливаем 0.")
                    data = torch.zeros_like(data)
                return data
            except Exception as e:
                print(f"[⚠️] Реальные данные недоступны: {e}. Переключаюсь на синтетику.")
                self.use_real_data = False   # отключаем реальные данные на будущее

        # Если нет изотопной модели, генерируем случайные данные
        if self.transitions is None:
            data = torch.randint(0, VOCAB_SIZE, (num_sequences, self.seq_len), device=DEVICE)
            return data

        # Генерация на основе изотопов (с контролем границ)
        tensors = torch.empty((num_sequences, self.seq_len), dtype=torch.long, device=DEVICE)
        current_states = torch.zeros(num_sequences, dtype=torch.long, device=DEVICE)

        for t in range(self.seq_len):
            probs = self.transitions[current_states]
            current_states = torch.multinomial(probs, 1).squeeze(1)
            t_starts = self.starts[current_states]
            t_lengths = self.lengths[current_states]
            offsets = (torch.rand(num_sequences, device=DEVICE) * t_lengths).long()
            values = t_starts + offsets
            # Обрезаем до допустимого диапазона
            values = values.clamp(0, VOCAB_SIZE-1)
            tensors[:, t] = values

        # Добавляем "спайки" (редкие выбросы)
        spike_mask = torch.rand((num_sequences, self.seq_len), device=DEVICE) < self.spike_prob
        tensors[spike_mask] = VOCAB_SIZE - 1

        # "Коллапс" — обнуление второй половины последовательности
        collapse_mask = torch.rand((num_sequences, 1), device=DEVICE) < self.collapse_prob
        half = self.seq_len // 2
        seq_indices = torch.arange(self.seq_len, device=DEVICE)
        collapse_region = collapse_mask.expand(-1, self.seq_len) & (seq_indices > half)
        tensors[collapse_region] = 0

        # Финальная проверка (на случай, если изотопы дают значения за пределами)
        tensors = tensors.clamp(0, VOCAB_SIZE-1)

        # Убедимся, что все значения в пределах словаря (если нет, заменим на 0)
        if tensors.max() >= VOCAB_SIZE:
            print(f"[ERROR] Синтетические данные вышли за границы словаря: max={tensors.max()}. Принудительно зануляем.")
            tensors[tensors >= VOCAB_SIZE] = 0

        return tensors