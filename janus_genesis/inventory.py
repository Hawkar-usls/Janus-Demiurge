# janus_genesis/inventory.py
"""
INVENTORY v2.1 — экипировка, слоты, сеты, расходники, автоприменение.
Добавлены поля knowledge (гиперпараметры) и fake (подделка).
"""

import random
import copy
from typing import Dict, List, Optional, Any, Tuple

# ========== КОНСТАНТЫ ==========
EQUIPMENT_SLOTS = [
    "head",      # шлем
    "chest",     # броня
    "legs",      # поножи
    "gloves",    # перчатки
    "boots",     # ботинки
    "cloak",     # плащ
    "weapon",    # оружие
    "offhand",   # щит/кинжал
    "ring1",     # кольцо 1
    "ring2",     # кольцо 2
    "necklace"   # амулет
]

# Бонусы сетов (пример)
SET_BONUSES = {
    "Neural Set": {
        2: {"n_embd": 32},
        3: {"n_layer": 1},
        4: {"gain": 0.2}
    },
    "Gradient Set": {
        2: {"gain": 0.15},
        3: {"lr": 0.0001},
        4: {"temperature": 0.2}
    },
    "Ancient Set": {
        2: {"n_head": 2},
        3: {"n_layer": 1},
        4: {"n_embd": 64}
    }
}

# Редкости предметов (для будущего)
RARITIES = ["common", "rare", "epic", "legendary"]


class Item:
    """
    Предмет: может быть экипировкой, расходником, артефактом.
    """
    def __init__(self,
                 name: str,
                 effect: Dict[str, Any],
                 weight: float = 1.0,
                 value: int = 10,
                 item_type: str = "equipment",   # equipment / consumable / artifact
                 slot: Optional[str] = None,
                 unique: bool = False,
                 stackable: bool = False,
                 max_stack: int = 1,
                 set_name: Optional[str] = None,
                 rarity: str = "common",
                 durability: Optional[int] = None,
                 durability_max: Optional[int] = None,
                 knowledge: Optional[Dict[str, Any]] = None,   # новое
                 fake: bool = False):                          # новое
        self.name = name
        self.effect = effect or {}
        self.weight = weight
        self.value = value
        self.item_type = item_type
        self.slot = slot
        self.unique = unique
        self.stackable = stackable
        self.max_stack = max_stack
        self.quantity = 1
        self.set_name = set_name
        self.rarity = rarity
        self.durability = durability
        self.durability_max = durability_max
        self.knowledge = knowledge or {}   # словарь гиперпараметров {'lr': 0.001}
        self.fake = fake

    def __repr__(self):
        return f"<Item {self.name} ({self.item_type})>"

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'effect': self.effect,
            'weight': self.weight,
            'value': self.value,
            'item_type': self.item_type,
            'slot': self.slot,
            'unique': self.unique,
            'stackable': self.stackable,
            'max_stack': self.max_stack,
            'quantity': self.quantity,
            'set_name': self.set_name,
            'rarity': self.rarity,
            'durability': self.durability,
            'durability_max': self.durability_max,
            'knowledge': self.knowledge,
            'fake': self.fake
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Item':
        item = cls(
            name=data['name'],
            effect=data['effect'],
            weight=data['weight'],
            value=data['value'],
            item_type=data['item_type'],
            slot=data['slot'],
            unique=data['unique'],
            stackable=data['stackable'],
            max_stack=data['max_stack'],
            set_name=data['set_name'],
            rarity=data['rarity'],
            durability=data['durability'],
            durability_max=data['durability_max'],
            knowledge=data.get('knowledge', {}),
            fake=data.get('fake', False)
        )
        item.quantity = data.get('quantity', 1)
        return item


class Inventory:
    """
    Инвентарь агента: список предметов + экипированные вещи.
    """
    def __init__(self, max_weight: float = 100.0):
        self.items: List[Item] = []                     # обычные предметы (в рюкзаке)
        self.equipment: Dict[str, Optional[Item]] = {slot: None for slot in EQUIPMENT_SLOTS}
        self.max_weight = max_weight

    # ---------- Базовые операции ----------
    def current_weight(self) -> float:
        """Текущий вес инвентаря (сумма веса всех предметов, включая экипированные)."""
        weight = sum(i.weight * i.quantity for i in self.items)
        for item in self.equipment.values():
            if item:
                weight += item.weight
        return weight

    def add_item(self, item: Item) -> bool:
        """Добавляет предмет в инвентарь (стеклит, если возможно)."""
        if self.current_weight() + item.weight > self.max_weight:
            return False

        # Стек с существующим
        if item.stackable:
            for existing in self.items:
                if existing.name == item.name and existing.stackable:
                    existing.quantity += item.quantity
                    return True

        self.items.append(item)
        return True

    def remove_item(self, item: Item, quantity: int = 1) -> bool:
        """Удаляет указанное количество предмета из инвентаря."""
        if item in self.items:
            if item.stackable:
                item.quantity -= quantity
                if item.quantity <= 0:
                    self.items.remove(item)
            else:
                self.items.remove(item)
            return True
        return False

    # ---------- Экипировка ----------
    def equip(self, item: Item) -> Tuple[bool, str]:
        """Надевает предмет в соответствующий слот."""
        if item.item_type != "equipment":
            return False, "Not equipable"
        if item.slot not in self.equipment:
            return False, "Invalid slot"

        current = self.equipment[item.slot]
        # Проверка уникальности: нельзя надеть два одинаковых уникальных
        if item.unique:
            for i in self.items:
                if i.name == item.name:
                    return False, "Already have this unique item"
            for eq in self.equipment.values():
                if eq and eq.name == item.name:
                    return False, "Already equipped"

        # Снимаем старый
        if current:
            if not self.add_item(current):
                return False, "Inventory full, cannot unequip current item"

        # Надеваем новый
        if item in self.items:
            self.items.remove(item)
        else:
            # если предмет уже в экипировке (переэкипировка?) — не должно быть
            pass
        self.equipment[item.slot] = item
        return True, f"Equipped {item.name}"

    def unequip(self, slot: str) -> Tuple[bool, str]:
        """Снимает предмет из слота в инвентарь."""
        if slot not in self.equipment:
            return False, "Invalid slot"
        item = self.equipment[slot]
        if not item:
            return False, "No item in slot"

        if self.current_weight() + item.weight > self.max_weight:
            return False, "Inventory full"
        self.items.append(item)
        self.equipment[slot] = None
        return True, f"Unequipped {item.name}"

    # ---------- Суммарные эффекты ----------
    def total_effects(self) -> Dict[str, Any]:
        """Суммирует эффекты от всей экипировки."""
        total = {}
        for item in self.equipment.values():
            if not item:
                continue
            for k, v in item.effect.items():
                total[k] = total.get(k, 0) + v
        return total

    def get_set_bonuses(self) -> Dict[str, Any]:
        """Считает бонусы от сетов."""
        set_counts = {}
        for item in self.equipment.values():
            if item and item.set_name:
                set_counts[item.set_name] = set_counts.get(item.set_name, 0) + 1

        bonuses = {}
        for set_name, count in set_counts.items():
            if set_name in SET_BONUSES:
                for pieces, effect in SET_BONUSES[set_name].items():
                    if count >= pieces:
                        for k, v in effect.items():
                            bonuses[k] = bonuses.get(k, 0) + v
        return bonuses

    def all_effects(self) -> Dict[str, Any]:
        """Полные эффекты: экипировка + сеты."""
        eff = self.total_effects()
        set_bonus = self.get_set_bonuses()
        for k, v in set_bonus.items():
            eff[k] = eff.get(k, 0) + v
        return eff

    # ---------- Расходники ----------
    def use_consumable(self, item: Item, target: Any) -> Tuple[bool, str]:
        """Применяет расходный предмет на цель (агента)."""
        if item.item_type != "consumable":
            return False, "Not a consumable"

        # Применяем эффекты на агента
        for k, v in item.effect.items():
            if hasattr(target, k):
                current = getattr(target, k)
                # Если это число, добавляем
                if isinstance(current, (int, float)):
                    setattr(target, k, current + v)
        # Уменьшаем количество
        item.quantity -= 1
        if item.quantity <= 0:
            self.remove_item(item)
        return True, f"Used {item.name}"

    # ---------- Умное авто-экипирование ----------
    def auto_equip_best(self) -> None:
        """Автоматически надевает лучшие предметы из инвентаря."""
        # Сортируем по ценности (value) — позже можно по score предсказания
        candidates = [i for i in self.items if i.item_type == "equipment"]
        candidates.sort(key=lambda x: x.value, reverse=True)

        for item in candidates:
            # Проверяем, есть ли слот
            if item.slot in self.equipment:
                current = self.equipment[item.slot]
                if not current or item.value > current.value:
                    self.equip(item)

    # ---------- Рынок / сохранение ----------
    def to_dict(self) -> Dict:
        return {
            'items': [item.to_dict() for item in self.items],
            'equipment': {slot: item.to_dict() if item else None for slot, item in self.equipment.items()},
            'max_weight': self.max_weight
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Inventory':
        inv = cls(max_weight=data.get('max_weight', 100))
        for item_data in data.get('items', []):
            inv.items.append(Item.from_dict(item_data))
        for slot, item_data in data.get('equipment', {}).items():
            if item_data:
                inv.equipment[slot] = Item.from_dict(item_data)
        return inv

    # ---------- Генерация случайных предметов ----------
    def random_item(self, rarity: str = "common") -> Item:
        """Создаёт случайный предмет (для тестов)."""
        # Базовые эффекты
        effects = {
            "common": {"gain": 0.05, "temperature": 0.05},
            "rare": {"gain": 0.1, "temperature": 0.1, "n_embd": 16},
            "epic": {"gain": 0.2, "temperature": 0.2, "n_embd": 32, "n_layer": 1},
            "legendary": {"gain": 0.3, "temperature": 0.3, "n_embd": 64, "n_layer": 2, "lr": 0.0001}
        }
        effect = effects.get(rarity, effects["common"])

        slots = EQUIPMENT_SLOTS
        slot = random.choice(slots)

        # Простое имя
        names = {
            "common": ["Cotton", "Leather", "Wooden"],
            "rare": ["Silver", "Gold", "Steel"],
            "epic": ["Mithril", "Crystal", "Dragon"],
            "legendary": ["Ancient", "Divine", "Void"]
        }
        prefix = random.choice(names.get(rarity, names["common"]))
        name = f"{prefix} {slot.capitalize()}"

        item = Item(
            name=name,
            effect=effect,
            weight=random.uniform(0.5, 3.0),
            value=random.randint(10, 200) * ({"common":1, "rare":2, "epic":4, "legendary":8}[rarity]),
            item_type="equipment",
            slot=slot,
            rarity=rarity,
            set_name=None,
            stackable=False
        )
        return item