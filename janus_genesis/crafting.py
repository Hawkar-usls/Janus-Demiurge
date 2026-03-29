# janus_genesis/crafting.py
import copy
from collections import Counter
from .inventory import Item

# База рецептов (можно расширять) – добавлены поля knowledge
RECIPES = {
    ("Attention Crystal", "Attention Crystal"): Item(
        name="Dual Attention Crystal",
        effect={"n_head": 4},
        weight=8,
        value=120,
        knowledge={"n_head": 4}
    ),
    ("Entropy Stone", "Entropy Stone"): Item(
        name="Entropy Cluster",
        effect={"temperature": 0.25},
        weight=5,
        value=80,
        knowledge={"temperature": 0.25}
    ),
    ("Optimizer Core", "Gradient Shard"): Item(
        name="Stabilized Optimizer",
        effect={"lr": -0.0002, "gain": 0.1},
        weight=5,
        value=150,
        knowledge={"lr": 0.001, "gain": 0.5}
    ),
    ("Embedding Relic", "Layer Fragment"): Item(
        name="Deep Relic",
        effect={"n_embd": 128, "n_layer": 2},
        weight=10,
        value=300,
        knowledge={"n_embd": 256, "n_layer": 1}
    ),
    ("Artifact of Evolution", "Entropy Stone", "Optimizer Core"): Item(
        name="Genesis Artifact",
        effect={"mutation_bonus": 0.5, "gain": 0.3, "temperature": 0.3},
        weight=2,
        value=1000,
        unique=True,
        knowledge={"mutation_bonus": 0.5, "gain": 0.3, "temperature": 0.3}
    ),
}

class CraftingSystem:
    def __init__(self, recipes=None):
        self.recipes = recipes if recipes else RECIPES

    def craft(self, agent, ingredient_names):
        """
        Пытается скрафтить предмет из списка имён ингредиентов.
        Возвращает (успех, сообщение, новый предмет или None).
        """
        # Проверяем, есть ли такой рецепт
        key = tuple(sorted(ingredient_names))
        if key not in self.recipes:
            return False, "Неизвестный рецепт", None

        # Проверяем, есть ли все ингредиенты у агента
        agent_item_names = [item.name for item in agent.inventory.items]
        need_counter = Counter(ingredient_names)
        for ing, count in need_counter.items():
            if agent_item_names.count(ing) < count:
                return False, f"Не хватает {ing}", None

        # Удаляем ингредиенты
        for ing, count in need_counter.items():
            removed = 0
            for item in agent.inventory.items[:]:  # итерируем по копии, чтобы можно было удалять
                if item.name == ing:
                    agent.remove_item(item)
                    removed += 1
                    if removed == count:
                        break

        # Создаём результат
        result_item = copy.deepcopy(self.recipes[key])
        agent.add_item(result_item)

        return True, f"Создан {result_item.name}", result_item