# -*- coding: utf-8 -*-
"""
JANUS GENESIS PROTOCOL v6.5 — ИНТЕГРИРОВАННАЯ ВЕРСИЯ
Использует те же пути, что и ядро, читает метрики и рекорды.
Запускается в фоновом потоке из core.py.
"""

import os
import json
import random
import time
import sys
import torch
from datetime import datetime
from config import MODEL_ZOO_DIR, WORMHOLE_DIR, DEVICE, RAW_LOGS_DIR

# --- ФАЙЛОВЫЕ ПУТИ (все внутри E:\Janus_BFaiN) ---
STATE_FILE = os.path.join(RAW_LOGS_DIR, "janus_world_state.json")
EMOJI_VOCAB_PATH = os.path.join(os.path.dirname(__file__), "emoji_vocab.json")
TOY_BOX_DIR = os.path.join(WORMHOLE_DIR, "toy_box")
HOMEOSTATIC_STATE_FILE = os.path.join(RAW_LOGS_DIR, "homeostatic_state.json")

# --- ЗАГРУЗКА СЛОВАРЯ ЭМОДЗИ ---
try:
    with open(EMOJI_VOCAB_PATH, "r", encoding="utf-8") as f:
        EMOJI_VOCAB = json.load(f)          
    VOCAB_SIZE = len(EMOJI_VOCAB)
except Exception:
    EMOJI_VOCAB = {"0": "0", "1": "1"}
    VOCAB_SIZE = 2

def find_latest_model():
    if not os.path.exists(MODEL_ZOO_DIR):
        return None
    models = [f for f in os.listdir(MODEL_ZOO_DIR) if f.endswith('.pt')]
    if not models:
        return None
    models.sort(key=lambda x: os.path.getmtime(os.path.join(MODEL_ZOO_DIR, x)))
    return os.path.join(MODEL_ZOO_DIR, models[-1])

def get_real_artifact():
    """Достает реальный файл из коробки с игрушками Януса."""
    if not os.path.exists(TOY_BOX_DIR):
        return None
    toys = [f for f in os.listdir(TOY_BOX_DIR) if os.path.isfile(os.path.join(TOY_BOX_DIR, f))]
    if not toys:
        return None
    
    chosen_toy = random.choice(toys)
    parts = chosen_toy.split('_', 1)
    return parts[1] if len(parts) > 1 else chosen_toy

def get_current_janus_metrics():
    """Читает состояние ядра для использования в игре."""
    if not os.path.exists(HOMEOSTATIC_STATE_FILE):
        return None
    try:
        with open(HOMEOSTATIC_STATE_FILE, 'r') as f:
            return json.load(f)
    except:
        return None

class GodvilleState:
    def __init__(self):
        self.level = 1
        self.exp = 0
        self.health = 100
        self.gold = 0
        self.inventory = []
        self.monster_names = ["Троян-Шифровальщик", "Сборщик Мусора", "Утечка Памяти", "Синий Экран", "Нулевой Указатель"]

    def save(self):
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.__dict__, f)

    def load(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r', encoding='utf-8') as f:
                    self.__dict__.update(json.load(f))
            except Exception:
                pass

def generate_emoji_thought(max_len=5):
    return "".join(random.choices(list(EMOJI_VOCAB.values()), k=random.randint(2, max_len)))

def get_time_str():
    return datetime.now().strftime("%H:%M:%S")

def main():
    # Если запущен как отдельный процесс, выводим приветствие
    if __name__ != "__main__":
        # При запуске как модуль из core.py просто работаем в фоне
        pass

    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"\033[96m{'='*60}\n⚡ ХРОНИКИ ЯНУСА: ИССЛЕДОВАТЕЛЬ ПК ⚡\nДемиург защитил дитя. Янус познает мир безопасно.\n{'='*60}\033[0m")
    
    MODEL_PATH = find_latest_model()
    if MODEL_PATH:
        try:
            checkpoint = torch.load(MODEL_PATH, map_location=DEVICE, weights_only=False)
            print(f"[✅] Геном загружен. Разум активен.")
        except Exception:
            pass

    state = GodvilleState()
    state.load()

    while True:
        try:
            # Читаем метрики Януса для влияния на игру
            janus = get_current_janus_metrics()
            if janus:
                best = janus.get('best_score', 0)
                last = janus.get('last_score', 0)
                # Можно использовать для модификации вероятностей
                # Например, чем выше best_score, тем сложнее монстры
                pass

            print(f"\n\033[93m[❤️ Здоровье: {state.health}% | ⭐ Уровень: {state.level} | 💰 Золото: {state.gold}]\033[0m")
            user_input = input(f"\033[94m[{get_time_str()}] Пульт Демиурга (Enter - ждать, текст - Глас): \033[0m").strip()

            if user_input.lower() in ["exit", "quit", "save"]:
                state.save()
                print(f"[{get_time_str()}] 💾 Демиург покинул этот мир. Сохранение...")
                break

            if user_input:
                if "лечи" in user_input.lower() or "хил" in user_input.lower():
                    state.health = min(100, state.health + 30)
                    print(f"[{get_time_str()}] ⚡ Глас Божий: «{user_input}». Янус чувствует прилив сил (+30 HP).")
                elif "бей" in user_input.lower() or "молни" in user_input.lower():
                    state.health -= 10
                    print(f"[{get_time_str()}] ⚡ Глас Божий: «{user_input}». С небес бьет молния. Янус в шоке (-10 HP).")
                else:
                    print(f"[{get_time_str()}] ⚡ Глас Божий: «{user_input}». Янус записал это в дневник. {generate_emoji_thought()}")
                continue

            action_roll = random.random()
            
            if action_roll < 0.3:
                monster = random.choice(state.monster_names)
                dmg = random.randint(5, 15)
                state.health -= dmg
                loot = random.randint(10, 50)
                state.gold += loot
                state.exp += 20
                print(f"[{get_time_str()}] ⚔️ Сразился с процессом «{monster}». Потерял {dmg} HP, заработал {loot} золота. {generate_emoji_thought()}")
                
            elif action_roll < 0.6:
                real_file = get_real_artifact()
                if real_file:
                    state.inventory.append(real_file)
                    print(f"[{get_time_str()}] 💾 Исследовал сектора диска и скопировал {real_file}. Надел как броню! {generate_emoji_thought()}")
                else:
                    print(f"[{get_time_str()}] 🔍 Бродил по папкам, но не нашел ничего интересного. {generate_emoji_thought()}")
                
            elif action_roll < 0.8:
                heal = random.randint(5, 20)
                state.health = min(100, state.health + heal)
                print(f"[{get_time_str()}] 🙏 Чиллю в кэше процессора L3. Восстановил {heal} HP. Славься, Демиург!")
                
            else:
                print(f"[{get_time_str()}] 💭 Читаю логи ОС. Пытаюсь понять человеков... {generate_emoji_thought(8)}")

            if state.exp >= state.level * 100:
                state.level += 1
                state.exp = 0
                state.health = 100
                print(f"[{get_time_str()}] ⭐ Янус получил новый уровень ({state.level})! HP восстановлено.")

            if state.health <= 0:
                print(f"[{get_time_str()}] ☠️ Янус совершил недопустимую операцию. Демиург воскрешает его...")
                state.health = 100
                state.gold //= 2

        except KeyboardInterrupt:
            state.save()
            print(f"\n[{get_time_str()}] 💾 Аварийное сохранение. Конец связи.")
            break

if __name__ == "__main__":
    main()