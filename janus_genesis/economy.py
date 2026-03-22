import random

class Market:
    """Рынок с динамическими ценами и листингами."""
    def __init__(self):
        self.listings = []          # список (seller_id, item, price, timestamp)
        self.price_history = {}     # item_name -> список цен
        self.base_prices = {
            "Attention Crystal": 50,
            "Entropy Stone": 30,
            "Optimizer Core": 40,
            "Embedding Relic": 80,
            "Gradient Shard": 20,
            "Layer Fragment": 100,
            "Artifact of Evolution": 500
        }

    def add_listing(self, seller_id, item, price):
        self.listings.append((seller_id, item, price, time.time()))

    def remove_listing(self, index):
        if 0 <= index < len(self.listings):
            return self.listings.pop(index)
        return None

    def get_current_price(self, item_name):
        """Возвращает среднюю цену за последние N сделок (или базовую)."""
        if item_name not in self.price_history or len(self.price_history[item_name]) < 5:
            return self.base_prices.get(item_name, 10)
        recent = self.price_history[item_name][-20:]
        return sum(recent) / len(recent)

    def record_transaction(self, item_name, price):
        if item_name not in self.price_history:
            self.price_history[item_name] = []
        self.price_history[item_name].append(price)
        if len(self.price_history[item_name]) > 100:
            self.price_history[item_name] = self.price_history[item_name][-100:]

    def suggest_price(self, item):
        """Рекомендованная цена для продажи (немного выше средней)."""
        base = self.get_current_price(item.name)
        return int(base * random.uniform(0.9, 1.1))


class Economy:
    """Экономика мира (ресурсы и рынок)."""

    def __init__(self):
        self.resources = {
            "compute": 10000,
            "data": 5000,
            "entropy": 2000
        }
        self.market = Market()
        self.tax_rate = 0.05  # 5% налог на сделки

    def spend(self, resource, amount):
        if self.resources.get(resource, 0) >= amount:
            self.resources[resource] -= amount
            return True
        return False

    def reward(self):
        """Случайная награда за рейд."""
        return {
            "compute": random.randint(10, 50),
            "data": random.randint(5, 20),
            "entropy": random.randint(1, 10)
        }

    def apply_reward(self, reward):
        for k, v in reward.items():
            self.resources[k] += v

    def can_afford(self, price):
        # для агентов проверка идёт через их gold
        pass